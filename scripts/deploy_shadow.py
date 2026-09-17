from __future__ import annotations

import json
import os
import pathlib
import re
import subprocess
from dataclasses import dataclass
from typing import Any, Callable

import cloudflare_provider as cf
import live_probe
import production_preflight as preflight

ROOT = pathlib.Path(__file__).resolve().parents[1]
MODE = "SHADOW_ACCEPTANCE"


class ShadowDeployError(RuntimeError):
    pass


@dataclass(frozen=True)
class WorkerSnapshot:
    exists: bool
    commit_sha: str | None
    deployment_mode: str | None
    deployment_id: str | None
    version_id: str | None


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True, stderr=subprocess.DEVNULL).strip()


def local_head() -> str:
    head = git("rev-parse", "HEAD").lower()
    if not re.fullmatch(r"[0-9a-f]{40}", head):
        raise ShadowDeployError("LOCAL_HEAD_INVALID")
    return head


def require_clean_exact_head(expected: str) -> str:
    if git("status", "--porcelain"):
        raise ShadowDeployError("DIRTY_WORKTREE")
    head = local_head()
    if head != expected.lower():
        raise ShadowDeployError("SHADOW_EXPECTED_HEAD_MISMATCH")
    return head


def d1_id() -> str:
    text = (ROOT / "wrangler.jsonc").read_text(encoding="utf-8")
    match = re.search(r'"database_id"\s*:\s*"([^"]+)"', text)
    return match.group(1) if match else ""


def _result(response: cf.Response) -> Any:
    if response.status != 200 or not isinstance(response.data, dict) or response.data.get("success") is not True:
        return None
    return response.data.get("result")


def worker_snapshot(api: Any, worker_name: str) -> WorkerSnapshot:
    settings = _result(api.get(f"/workers/scripts/{worker_name}/settings"))
    deployments = _result(api.get(f"/workers/scripts/{worker_name}/deployments"))
    if not isinstance(settings, dict) or deployments is None:
        return WorkerSnapshot(False, None, None, None, None)
    bindings = [item for item in (settings.get("bindings") or []) if isinstance(item, dict)]
    commit = cf._binding_value(bindings, "FARE_COMMIT_SHA")
    mode = cf._binding_value(bindings, "FARE_DEPLOYMENT_MODE")
    try:
        deployment_id, versions = cf._deployment_versions(deployments)
        version_id = str(versions[0]["version_id"])
    except cf.CloudflareProviderError:
        deployment_id = None
        version_id = None
    return WorkerSnapshot(True, str(commit) if commit is not None else None, str(mode) if mode is not None else None, deployment_id, version_id)


def _run(runner: Callable[..., Any], args: list[str], *, timeout: int) -> Any:
    return runner(args, cwd=ROOT, text=True, capture_output=True, timeout=timeout, check=False)


def _required_env() -> dict[str, str]:
    names = [
        "CLOUDFLARE_API_TOKEN", "CLOUDFLARE_ACCOUNT_ID", "FARE_D1_DATABASE_ID",
        "FARE_WORKER_TOKEN", "FARE_SHADOW_REVIEWER_KEY_ID", "FARE_SHADOW_REVIEWER_SECRET",
        "FARE_ACCESS_REVIEWER_KEY_ID", "FARE_ACCESS_REVIEWER_SECRET",
    ]
    values = {name: os.environ.get(name, "") for name in names}
    if not all(values.values()):
        raise ShadowDeployError("SHADOW_DEPLOY_ENV_INCOMPLETE")
    return values


def deploy_shadow(
    *,
    runner: Callable[..., Any] = subprocess.run,
    api_factory: Callable[[str, str], Any] = cf.CloudflareApi,
    readback: Callable[..., dict[str, Any]] = cf.collect_bootstrap_readback,
    probes: Callable[..., dict[str, Any]] = live_probe.run_probes,
) -> dict[str, Any]:
    expected = os.environ.get("FARE_SHADOW_EXPECTED_HEAD", "").lower()
    if not re.fullmatch(r"[0-9a-f]{40}", expected):
        raise ShadowDeployError("FARE_SHADOW_EXPECTED_HEAD_REQUIRED")
    head = require_clean_exact_head(expected)
    if not preflight.code_ready(head):
        raise ShadowDeployError("LOCAL_CODE_GATES_NOT_READY")
    configured_d1 = d1_id()
    if configured_d1 in preflight.PLACEHOLDERS:
        raise ShadowDeployError("D1_DATABASE_ID_MISSING")
    values = _required_env()
    if values["FARE_D1_DATABASE_ID"] != configured_d1:
        raise ShadowDeployError("D1_DATABASE_ID_ENV_MISMATCH")
    worker_name = os.environ.get("FARE_CLOUDFLARE_WORKER_NAME", "fare-radar")

    build = _run(runner, ["npm", "run", "build"], timeout=180)
    if getattr(build, "returncode", 1) != 0:
        raise ShadowDeployError("SHADOW_BUILD_FAILED")

    api = api_factory(values["CLOUDFLARE_ACCOUNT_ID"], values["CLOUDFLARE_API_TOKEN"])
    before = worker_snapshot(api, worker_name)
    command = [
        "npx", "--yes", "wrangler@4.131.2", "deploy", "--config", "wrangler.jsonc",
        "--keep-vars", "--strict",
        "--var", f"FARE_COMMIT_SHA:{head}",
        "--var", f"FARE_DEPLOYMENT_MODE:{MODE}",
    ]
    deploy_unknown = False
    try:
        result = _run(runner, command, timeout=240)
        deploy_unknown = getattr(result, "returncode", 1) != 0
    except subprocess.TimeoutExpired:
        deploy_unknown = True

    try:
        state = readback(
            api,
            account_id=values["CLOUDFLARE_ACCOUNT_ID"],
            database_id=configured_d1,
            worker_name=worker_name,
            expected_head=head,
            expected_mode=MODE,
        )
    except cf.CloudflareProviderError as exc:
        after = worker_snapshot(api, worker_name)
        if after == before:
            raise ShadowDeployError("SHADOW_DEPLOY_NOT_APPLIED") from exc
        raise ShadowDeployError("SHADOW_DEPLOY_PARTIAL_OR_AMBIGUOUS") from exc

    probe_result = probes(
        base_url=state["worker_origin"],
        expected_head=head,
        expected_mode=MODE,
        worker_token=values["FARE_WORKER_TOKEN"],
        shadow_key_id=values["FARE_SHADOW_REVIEWER_KEY_ID"],
        shadow_secret=values["FARE_SHADOW_REVIEWER_SECRET"],
        access_key_id=values["FARE_ACCESS_REVIEWER_KEY_ID"],
        access_secret=values["FARE_ACCESS_REVIEWER_SECRET"],
    )
    cf.write_bootstrap_evidence(state)
    return {
        "ok": True,
        "commit_sha": head,
        "deployment_mode": MODE,
        "version_id": state["version_id"],
        "deploy_command_uncertain_but_readback_confirmed": deploy_unknown,
        "live_probes": probe_result,
        "provider_readback_stage": "BOOTSTRAP_ONLY",
        "next_gate": "HUMAN_ACCESS_REVIEW_THEN_FULL_CLOUDFLARE_READBACK",
    }


def main() -> int:
    try:
        result = deploy_shadow()
        print(json.dumps(result, sort_keys=True))
        return 0
    except ShadowDeployError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
