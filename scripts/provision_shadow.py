from __future__ import annotations

import json
import os
import pathlib
import re
import subprocess
import tempfile
import time
import urllib.parse
from dataclasses import dataclass
from typing import Any, Callable

import cloudflare_provider as cf
import d1_recovery as d1r
import github_provider as gh

ROOT = pathlib.Path(__file__).resolve().parents[1]
DB_NAME = "fare-radar-production"
WRANGLER = "wrangler@4.131.2"
HEAD_RE = re.compile(r"^[0-9a-f]{40}$")
UUID_RE = re.compile(r"^[0-9a-fA-F-]{32,36}$")


class ShadowProvisionError(RuntimeError):
    pass


@dataclass(frozen=True)
class D1Identity:
    database_id: str
    name: str
    reused: bool


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True, stderr=subprocess.DEVNULL).strip()


def _run(runner: Callable[..., Any], args: list[str], *, timeout: int, env: dict[str, str] | None = None) -> Any:
    merged = os.environ.copy()
    merged["CI"] = "true"
    if env:
        merged.update(env)
    return runner(args, cwd=ROOT, text=True, capture_output=True, timeout=timeout, check=False, env=merged)


def _ok(response: cf.Response, code: str) -> Any:
    if response.status not in (200, 201) or not isinstance(response.data, dict) or response.data.get("success") is not True:
        raise ShadowProvisionError(code)
    return response.data.get("result")


def _list_named_d1(api: Any, name: str = DB_NAME) -> list[dict[str, Any]]:
    query = urllib.parse.urlencode({"name": name, "per_page": 100})
    result = _ok(api.get(f"/d1/database?{query}"), "D1_LIST_READBACK_FAILED")
    rows = result if isinstance(result, list) else []
    exact = [row for row in rows if isinstance(row, dict) and row.get("name") == name]
    if len(exact) > 1:
        raise ShadowProvisionError("D1_NAME_IDENTITY_AMBIGUOUS")
    return exact


def _identity(row: dict[str, Any], *, reused: bool) -> D1Identity:
    database_id = str(row.get("uuid") or row.get("id") or "")
    name = str(row.get("name") or "")
    if name != DB_NAME or not UUID_RE.fullmatch(database_id):
        raise ShadowProvisionError("D1_IDENTITY_INVALID")
    return D1Identity(database_id=database_id, name=name, reused=reused)


def ensure_d1(api: Any) -> D1Identity:
    before = _list_named_d1(api)
    if before:
        return _identity(before[0], reused=True)
    create_error: Exception | None = None
    try:
        response = api.post("/d1/database", {"name": DB_NAME})
        result = _ok(response, "D1_CREATE_REJECTED")
        if isinstance(result, dict):
            created = _identity(result, reused=False)
            after = _list_named_d1(api)
            if len(after) == 1 and _identity(after[0], reused=True).database_id == created.database_id:
                return created
            raise ShadowProvisionError("D1_CREATE_POSTREADBACK_MISMATCH")
    except (cf.CloudflareProviderError, ShadowProvisionError) as exc:
        if isinstance(exc, ShadowProvisionError) and str(exc) not in {"D1_CREATE_REJECTED", "D1_CREATE_POSTREADBACK_MISMATCH"}:
            raise
        create_error = exc
    after_unknown = _list_named_d1(api)
    if len(after_unknown) == 1:
        return _identity(after_unknown[0], reused=False)
    if not after_unknown:
        raise ShadowProvisionError("D1_CREATE_NOT_APPLIED") from create_error
    raise ShadowProvisionError("D1_CREATE_PARTIAL_OR_AMBIGUOUS") from create_error


def _query_rows(api: Any, database_id: str, sql: str) -> list[dict[str, Any]]:
    return cf._query_rows(api, database_id, sql)


def migration_state(api: Any, database_id: str) -> list[str]:
    tables = _query_rows(api, database_id, "SELECT name FROM sqlite_master WHERE type='table' AND name='d1_migrations'")
    if not tables:
        return []
    return [str(row.get("name")) for row in _query_rows(api, database_id, "SELECT name FROM d1_migrations ORDER BY id")]


def _require_prefix(current: list[str], expected: list[str]) -> None:
    if current != expected[: len(current)]:
        raise ShadowProvisionError("D1_MIGRATION_HISTORY_DRIFT")


def render_config(database_id: str, path: pathlib.Path) -> None:
    data = json.loads((ROOT / "wrangler.jsonc").read_text(encoding="utf-8"))
    bindings = data.get("d1_databases")
    if not isinstance(bindings, list) or len(bindings) != 1 or bindings[0].get("binding") != "DB" or bindings[0].get("database_name") != DB_NAME:
        raise ShadowProvisionError("WRANGLER_D1_BINDING_SHAPE_INVALID")
    bindings[0]["database_id"] = database_id
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def ensure_migrations(api: Any, database_id: str, config_path: pathlib.Path, *, runner: Callable[..., Any] = subprocess.run) -> str:
    expected = cf._migration_names()
    before = migration_state(api, database_id)
    _require_prefix(before, expected)
    if before == expected:
        return "already_applied"
    pending = d1r.pending_migration_names(before, expected)
    try:
        d1r.require_expand_only(pending)
        bookmark = d1r.current_bookmark(api, database_id)
    except d1r.D1RecoveryError as exc:
        raise ShadowProvisionError(str(exc)) from exc
    recovery_doc = d1r.recovery_manifest(
        database_id=database_id,
        before=before,
        pending=pending,
        bookmark=bookmark,
    )
    d1r.write_manifest(recovery_doc)
    command = ["npx", "--yes", WRANGLER, "d1", "migrations", "apply", DB_NAME, "--remote", "--config", str(config_path)]
    uncertain = False
    try:
        result = _run(runner, command, timeout=300)
        uncertain = getattr(result, "returncode", 1) != 0
    except subprocess.TimeoutExpired:
        uncertain = True
    after = migration_state(api, database_id)
    recovery_doc["after_migrations"] = after
    d1r.write_manifest(recovery_doc)
    if after == expected:
        return "readback_confirmed" if uncertain else "applied"
    if after == before:
        raise ShadowProvisionError("D1_MIGRATIONS_NOT_APPLIED")
    raise ShadowProvisionError("D1_MIGRATIONS_PARTIAL_OR_AMBIGUOUS")


def baseline_state(api: Any, database_id: str) -> tuple[set[str], set[str]]:
    source_ids = {str(row.get("source_id")) for row in _query_rows(api, database_id, "SELECT source_id FROM source_registry")}
    provider_ids = {str(row.get("provider_id")) for row in _query_rows(api, database_id, "SELECT provider_id FROM provider_access_registry")}
    return source_ids, provider_ids


def baseline_expected() -> tuple[set[str], set[str]]:
    return (
        cf._seed_ids(ROOT / "config" / "sources.seed.json", "source_id"),
        cf._seed_ids(ROOT / "config" / "providers.seed.json", "provider_id"),
    )


def baseline_complete(state: tuple[set[str], set[str]]) -> bool:
    expected_sources, expected_providers = baseline_expected()
    sources, providers = state
    return expected_sources <= sources and expected_providers <= providers


def ensure_seed(api: Any, database_id: str, config_path: pathlib.Path, *, runner: Callable[..., Any] = subprocess.run) -> str:
    before = baseline_state(api, database_id)
    if baseline_complete(before):
        return "already_applied"
    command = ["npx", "--yes", WRANGLER, "d1", "execute", DB_NAME, "--remote", "--file", "generated/seed.generated.sql", "--config", str(config_path)]
    uncertain = False
    try:
        result = _run(runner, command, timeout=300)
        uncertain = getattr(result, "returncode", 1) != 0
    except subprocess.TimeoutExpired:
        uncertain = True
    after = baseline_state(api, database_id)
    if baseline_complete(after):
        return "readback_confirmed" if uncertain else "applied"
    if after == before:
        raise ShadowProvisionError("D1_SEED_NOT_APPLIED")
    raise ShadowProvisionError("D1_SEED_PARTIAL_OR_AMBIGUOUS")


def github_target_precheck(api: Any, repository: str, expected_head: str) -> dict[str, Any]:
    if not getattr(api, "token", None):
        raise ShadowProvisionError("GITHUB_WRITE_TOKEN_REQUIRED")
    repo = gh._require_ok(api.get(""), "GITHUB_REPOSITORY_READBACK_FAILED")
    if repo.get("full_name") != repository or repo.get("private") is not False or repo.get("default_branch") != "main":
        raise ShadowProvisionError("GITHUB_REPOSITORY_IDENTITY_MISMATCH")
    branch = gh._require_ok(api.get("/branches/main"), "GITHUB_MAIN_READBACK_FAILED")
    if str(((branch.get("commit") or {}).get("sha") or "")).lower() != expected_head:
        raise ShadowProvisionError("GITHUB_MAIN_HEAD_MISMATCH")
    runs = gh._require_ok(api.get(f"/actions/runs?head_sha={expected_head}&per_page=50"), "GITHUB_CI_READBACK_FAILED").get("workflow_runs", [])
    exact = [
        row for row in runs
        if isinstance(row, dict)
        and row.get("head_sha") == expected_head
        and row.get("head_branch") == "main"
        and row.get("path") == ".github/workflows/ci.yml"
        and row.get("status") == "completed"
        and row.get("conclusion") == "success"
    ]
    if not exact:
        raise ShadowProvisionError("GITHUB_MAIN_EXACT_HEAD_CI_MISSING")
    exact.sort(key=lambda row: int(row.get("run_number") or 0), reverse=True)
    return {"repository": repository, "head": expected_head, "ci_run_id": exact[0].get("id")}


def run_local_acceptance(*, runner: Callable[..., Any] = subprocess.run) -> None:
    result = _run(runner, ["npm", "run", "check:prepush"], timeout=1200)
    if getattr(result, "returncode", 1) != 0:
        raise ShadowProvisionError("LOCAL_PREPUSH_ACCEPTANCE_FAILED")


def tracked_binding() -> str:
    data = json.loads((ROOT / "wrangler.jsonc").read_text(encoding="utf-8"))
    rows = data.get("d1_databases") or []
    if len(rows) != 1:
        raise ShadowProvisionError("WRANGLER_D1_BINDING_SHAPE_INVALID")
    return str(rows[0].get("database_id") or "")


def bind_and_commit(database_id: str, *, runner: Callable[..., Any] = subprocess.run) -> str:
    current = tracked_binding()
    if current == database_id:
        if git("status", "--porcelain"):
            raise ShadowProvisionError("BOUND_CONFIG_DIRTY_WORKTREE")
        return git("rev-parse", "HEAD").lower()
    if current not in {"", "REPLACE_WITH_D1_DATABASE_ID"}:
        raise ShadowProvisionError("WRANGLER_D1_BINDING_CONFLICT")
    if git("status", "--porcelain"):
        raise ShadowProvisionError("DIRTY_WORKTREE_BEFORE_BINDING")
    render_config(database_id, ROOT / "wrangler.jsonc")
    changed = git("diff", "--name-only").splitlines()
    if changed != ["wrangler.jsonc"]:
        raise ShadowProvisionError("UNEXPECTED_RELEASE_DIFF")
    for command in (["git", "add", "wrangler.jsonc"], ["git", "commit", "-m", "bind production D1 for shadow provisioning"]):
        result = _run(runner, list(command), timeout=120)
        if getattr(result, "returncode", 1) != 0:
            raise ShadowProvisionError("RELEASE_BINDING_COMMIT_FAILED")
    head = git("rev-parse", "HEAD").lower()
    if not HEAD_RE.fullmatch(head) or git("status", "--porcelain"):
        raise ShadowProvisionError("RELEASE_BINDING_COMMIT_INVALID")
    return head


def generate_gate_evidence(*, runner: Callable[..., Any] = subprocess.run) -> None:
    commands: list[list[str]] = []
    for stage in range(5):
        commands.append(["python3", "scripts/gate_evidence.py", "--stage", str(stage)])
    for stage in range(5):
        commands.append(["python3", "scripts/gate_evidence.py", "--suite-stage", str(stage)])
    commands.append(["python3", "scripts/gate_evidence.py", "--finalize"])
    for command in commands:
        result = _run(runner, command, timeout=1200)
        if getattr(result, "returncode", 1) != 0:
            raise ShadowProvisionError("RELEASE_GATE_EVIDENCE_FAILED")


def _branch_sha(api: Any, branch: str) -> str | None:
    encoded = urllib.parse.quote(branch, safe="")
    response = api.get(f"/branches/{encoded}")
    if response.status == 404:
        return None
    data = gh._require_ok(response, "GITHUB_RELEASE_BRANCH_READBACK_FAILED")
    return str(((data.get("commit") or {}).get("sha") or "")).lower() or None


def push_release_branch(api: Any, release_head: str, *, runner: Callable[..., Any] = subprocess.run, branch: str | None = None) -> str:
    branch = branch or f"shadow-release-{release_head[:12]}"
    before = _branch_sha(api, branch)
    if before == release_head:
        return branch
    if before is not None:
        raise ShadowProvisionError("GITHUB_RELEASE_BRANCH_CONFLICT")
    command = ["git", "push", "origin", f"HEAD:refs/heads/{branch}"]
    uncertain = False
    try:
        result = _run(runner, command, timeout=180)
        uncertain = getattr(result, "returncode", 1) != 0
    except subprocess.TimeoutExpired:
        uncertain = True
    after = _branch_sha(api, branch)
    if after == release_head:
        return branch
    if after is None:
        raise ShadowProvisionError("GITHUB_RELEASE_BRANCH_NOT_APPLIED")
    raise ShadowProvisionError("GITHUB_RELEASE_BRANCH_PARTIAL_OR_AMBIGUOUS" if uncertain else "GITHUB_RELEASE_BRANCH_POSTREADBACK_MISMATCH")


def wait_exact_ci(api: Any, head: str, branch: str, *, timeout_seconds: int = 300, sleep: Callable[[float], None] = time.sleep) -> int:
    deadline = time.time() + timeout_seconds
    while True:
        data = gh._require_ok(api.get(f"/actions/runs?head_sha={head}&per_page=50"), "GITHUB_CI_READBACK_FAILED")
        rows = [
            row for row in data.get("workflow_runs", [])
            if isinstance(row, dict) and row.get("head_sha") == head and row.get("head_branch") == branch and row.get("path") == ".github/workflows/ci.yml"
        ]
        success = [row for row in rows if row.get("status") == "completed" and row.get("conclusion") == "success"]
        if success:
            success.sort(key=lambda row: int(row.get("run_number") or 0), reverse=True)
            return int(success[0].get("id") or 0)
        terminal_bad = [row for row in rows if row.get("status") == "completed" and row.get("conclusion") not in (None, "success")]
        if terminal_bad:
            raise ShadowProvisionError("GITHUB_RELEASE_EXACT_HEAD_CI_FAILED")
        if time.time() >= deadline:
            raise ShadowProvisionError("GITHUB_RELEASE_EXACT_HEAD_CI_TIMEOUT")
        sleep(5)


def prepare_shadow_release(*, runner: Callable[..., Any] = subprocess.run, cf_api_factory: Callable[[str, str], Any] = cf.CloudflareApi, gh_api_factory: Callable[[str, str | None], Any] = gh.GitHubApi) -> dict[str, Any]:
    repository = os.environ.get("FARE_GITHUB_REPOSITORY", "")
    base_head = os.environ.get("FARE_PROVISION_EXPECTED_HEAD", "").lower()
    account_id = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "")
    cf_token = os.environ.get("CLOUDFLARE_API_TOKEN", "")
    gh_token = os.environ.get("FARE_GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or ""
    if not gh.REPO_RE.fullmatch(repository) or not HEAD_RE.fullmatch(base_head):
        raise ShadowProvisionError("SHADOW_PROVISION_GITHUB_TARGET_REQUIRED")
    if not account_id or not cf_token or not gh_token:
        raise ShadowProvisionError("SHADOW_PROVISION_PROVIDER_CREDENTIALS_REQUIRED")
    gh.require_local_identity(repository, base_head)
    run_local_acceptance(runner=runner)
    gh_api = gh_api_factory(repository, gh_token)
    github_target_precheck(gh_api, repository, base_head)
    cf_api = cf_api_factory(account_id, cf_token)
    identity = ensure_d1(cf_api)
    with tempfile.TemporaryDirectory(prefix="fare-radar-provision-") as tmp:
        temp_config = pathlib.Path(tmp) / "wrangler.provision.jsonc"
        render_config(identity.database_id, temp_config)
        migration_result = ensure_migrations(cf_api, identity.database_id, temp_config, runner=runner)
        seed_result = ensure_seed(cf_api, identity.database_id, temp_config, runner=runner)
    release_head = bind_and_commit(identity.database_id, runner=runner)
    generate_gate_evidence(runner=runner)
    release_branch = push_release_branch(gh_api, release_head, runner=runner)
    ci_run_id = wait_exact_ci(gh_api, release_head, release_branch)
    return {
        "ok": True,
        "phase": "SHADOW_RELEASE_CANDIDATE_READY",
        "database_id": identity.database_id,
        "database_reused": identity.reused,
        "migrations": migration_result,
        "seed": seed_result,
        "release_head": release_head,
        "release_branch": release_branch,
        "ci_run_id": ci_run_id,
        "next_gate": "GITHUB_PROTECTION_AND_SHADOW_RUNTIME_BOOTSTRAP",
    }


def main() -> int:
    try:
        print(json.dumps(prepare_shadow_release(), sort_keys=True))
        return 0
    except (ShadowProvisionError, gh.GitHubProviderError, cf.CloudflareProviderError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
