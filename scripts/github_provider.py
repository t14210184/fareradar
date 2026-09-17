from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import pathlib
import re
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]
HEAD_RE = re.compile(r"^[0-9a-f]{40}$")
REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


class GitHubProviderError(RuntimeError):
    pass


@dataclass
class Response:
    status: int
    data: Any


class GitHubApi:
    def __init__(self, repository: str, token: str | None = None, timeout: float = 20.0):
        self.repository = repository
        self.token = token
        self.timeout = timeout
        self.base = f"https://api.github.com/repos/{repository}"

    def request(self, method: str, path: str, payload: Any | None = None) -> Response:
        body = None if payload is None else json.dumps(payload, separators=(",", ":")).encode()
        headers = {
            "accept": "application/vnd.github+json",
            "x-github-api-version": "2022-11-28",
            "user-agent": "fare-radar-v1.3",
        }
        if self.token:
            headers["authorization"] = f"Bearer {self.token}"
        if body is not None:
            headers["content-type"] = "application/json"
        req = urllib.request.Request(self.base + path, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                raw = response.read().decode()
                return Response(response.status, json.loads(raw) if raw else None)
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode(errors="replace")
            try:
                data = json.loads(raw) if raw else None
            except json.JSONDecodeError:
                data = {"raw": raw}
            return Response(exc.code, data)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise GitHubProviderError("GITHUB_TRANSPORT_UNKNOWN") from exc

    def get(self, path: str) -> Response:
        return self.request("GET", path)

    def patch(self, path: str, payload: Any) -> Response:
        return self.request("PATCH", path, payload)

    def post(self, path: str, payload: Any | None = None) -> Response:
        return self.request("POST", path, payload)

    def put(self, path: str, payload: Any) -> Response:
        return self.request("PUT", path, payload)


def evidence_path() -> pathlib.Path:
    raw = os.environ.get("FARE_EVIDENCE_ROOT", "")
    root = ROOT / "evidence" if not raw else pathlib.Path(raw).expanduser()
    if raw and not root.is_absolute():
        raise GitHubProviderError("FARE_EVIDENCE_ROOT_MUST_BE_ABSOLUTE")
    return root / "provider" / "github-readback.json"


def env_target() -> tuple[str, str]:
    repo = os.environ.get("FARE_GITHUB_REPOSITORY", "")
    head = os.environ.get("FARE_GITHUB_EXPECTED_HEAD", "").lower()
    if not REPO_RE.fullmatch(repo):
        raise GitHubProviderError("GITHUB_REPOSITORY_REQUIRED")
    if not HEAD_RE.fullmatch(head):
        raise GitHubProviderError("GITHUB_EXPECTED_HEAD_REQUIRED")
    return repo, head


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True, stderr=subprocess.DEVNULL).strip()


def require_local_identity(repo: str, expected: str) -> None:
    if git("status", "--porcelain"):
        raise GitHubProviderError("DIRTY_WORKTREE")
    if git("rev-parse", "HEAD").lower() != expected:
        raise GitHubProviderError("LOCAL_HEAD_MISMATCH")
    remote = git("remote", "get-url", "origin")
    normalized = remote.removesuffix(".git")
    accepted = {f"https://github.com/{repo}", f"git@github.com:{repo}", f"ssh://git@github.com/{repo}"}
    if normalized not in accepted:
        raise GitHubProviderError("GITHUB_REMOTE_TARGET_MISMATCH")


def _require_ok(response: Response, code: str) -> Any:
    if response.status != 200 or not isinstance(response.data, dict):
        raise GitHubProviderError(code)
    return response.data


def _contexts(protection: dict[str, Any]) -> list[str]:
    required = protection.get("required_status_checks") or {}
    values = {x for x in required.get("contexts", []) if isinstance(x, str)}
    for item in required.get("checks", []) or []:
        if isinstance(item, dict) and isinstance(item.get("context"), str):
            values.add(item["context"])
    return sorted(values)


def _flag(protection: dict[str, Any], name: str) -> bool:
    value = protection.get(name)
    if isinstance(value, dict):
        return value.get("enabled") is True
    return value is True


def _identity_and_ci(api: Any, repository: str, expected: str) -> tuple[dict[str, Any], dict[str, Any]]:
    repo = _require_ok(api.get(""), "GITHUB_REPOSITORY_READBACK_FAILED")
    if repo.get("full_name") != repository or repo.get("private") is not False or repo.get("default_branch") != "main":
        raise GitHubProviderError("GITHUB_REPOSITORY_IDENTITY_MISMATCH")
    branch = _require_ok(api.get("/branches/main"), "GITHUB_MAIN_READBACK_FAILED")
    main_sha = str(((branch.get("commit") or {}).get("sha") or "")).lower()
    if main_sha != expected:
        raise GitHubProviderError("GITHUB_MAIN_HEAD_MISMATCH")
    runs = _require_ok(
        api.get("/actions/runs?head_sha=" + expected + "&per_page=50"),
        "GITHUB_CI_READBACK_FAILED",
    ).get("workflow_runs", [])
    exact = [
        row
        for row in runs
        if isinstance(row, dict)
        and row.get("head_sha") == expected
        and row.get("path") == ".github/workflows/ci.yml"
        and row.get("status") == "completed"
        and row.get("conclusion") == "success"
    ]
    if not exact:
        raise GitHubProviderError("GITHUB_EXACT_HEAD_CI_MISSING")
    exact.sort(key=lambda row: int(row.get("run_number") or 0), reverse=True)
    return repo, exact[0]


def _read_protection(api: Any) -> dict[str, Any]:
    response = api.get("/branches/main/protection")
    if response.status == 403:
        raise GitHubProviderError("GITHUB_BRANCH_PROTECTION_ADMIN_PERMISSION_REQUIRED")
    if response.status == 404:
        raise GitHubProviderError("GITHUB_BRANCH_PROTECTION_MISSING")
    return _require_ok(response, "GITHUB_BRANCH_PROTECTION_READBACK_FAILED")


def _protection_safe(protection: dict[str, Any]) -> bool:
    required = protection.get("required_status_checks") or {}
    return (
        "test" in _contexts(protection)
        and required.get("strict") is True
        and _flag(protection, "enforce_admins")
        and not _flag(protection, "allow_force_pushes")
        and not _flag(protection, "allow_deletions")
    )


def read_state(api: Any, repository: str, expected: str) -> dict[str, Any]:
    repo, exact_ci = _identity_and_ci(api, repository, expected)
    protection = _read_protection(api)
    contexts = _contexts(protection)
    if "test" not in contexts:
        raise GitHubProviderError("GITHUB_REQUIRED_TEST_CONTEXT_MISSING")
    required = protection.get("required_status_checks") or {}
    if required.get("strict") is not True:
        raise GitHubProviderError("GITHUB_REQUIRED_STATUS_STRICT_MISSING")
    if not _flag(protection, "enforce_admins"):
        raise GitHubProviderError("GITHUB_ADMIN_ENFORCEMENT_MISSING")
    if _flag(protection, "allow_force_pushes"):
        raise GitHubProviderError("GITHUB_FORCE_PUSH_ALLOWED")
    if _flag(protection, "allow_deletions"):
        raise GitHubProviderError("GITHUB_BRANCH_DELETION_ALLOWED")
    return {
        "provider": "github",
        "repository_id": repo.get("id"),
        "repository_full_name": repository,
        "visibility": "public",
        "default_branch": "main",
        "commit_sha": expected,
        "ci_run_id": exact_ci.get("id"),
        "ci_conclusion": "success",
        "required_status_contexts": contexts,
        "required_status_strict": True,
        "admin_enforcement": True,
        "force_pushes_allowed": False,
        "branch_deletions_allowed": False,
        "branch_protection_verified": True,
        "observed_at": dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z"),
    }


def write_evidence(state: dict[str, Any]) -> None:
    path = evidence_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _new_protection_payload() -> dict[str, Any]:
    return {
        "required_status_checks": {"strict": True, "contexts": ["test"]},
        "enforce_admins": True,
        "required_pull_request_reviews": None,
        "restrictions": None,
        "required_linear_history": True,
        "allow_force_pushes": False,
        "allow_deletions": False,
        "block_creations": False,
        "required_conversation_resolution": False,
        "lock_branch": False,
        "allow_fork_syncing": False,
    }


def _readback_after_unknown(api: Any, predicate: Any, not_applied: str, ambiguous: str) -> dict[str, Any]:
    response = api.get("/branches/main/protection")
    if response.status == 404:
        raise GitHubProviderError(not_applied)
    if response.status != 200 or not isinstance(response.data, dict):
        raise GitHubProviderError(ambiguous)
    if predicate(response.data):
        return response.data
    raise GitHubProviderError(ambiguous)


def ensure_protection(api: Any, repository: str, expected: str) -> dict[str, Any]:
    if not getattr(api, "token", None):
        raise GitHubProviderError("GITHUB_ADMIN_TOKEN_REQUIRED")
    _identity_and_ci(api, repository, expected)
    response = api.get("/branches/main/protection")
    if response.status == 403:
        raise GitHubProviderError("GITHUB_BRANCH_PROTECTION_ADMIN_PERMISSION_REQUIRED")
    if response.status == 404:
        try:
            created = api.put("/branches/main/protection", _new_protection_payload())
        except GitHubProviderError as exc:
            if str(exc) != "GITHUB_TRANSPORT_UNKNOWN":
                raise
            _readback_after_unknown(
                api,
                _protection_safe,
                "GITHUB_BRANCH_PROTECTION_UNKNOWN_NOT_APPLIED",
                "GITHUB_BRANCH_PROTECTION_PARTIAL_OR_AMBIGUOUS",
            )
        else:
            if created.status == 403:
                raise GitHubProviderError("GITHUB_BRANCH_PROTECTION_ADMIN_PERMISSION_REQUIRED")
            if created.status != 200:
                raise GitHubProviderError("GITHUB_BRANCH_PROTECTION_CREATE_REJECTED")
        protection = _read_protection(api)
        if not _protection_safe(protection):
            raise GitHubProviderError("GITHUB_BRANCH_PROTECTION_POSTREADBACK_MISMATCH")
    elif response.status == 200 and isinstance(response.data, dict):
        protection = response.data
        if _flag(protection, "allow_force_pushes") or _flag(protection, "allow_deletions"):
            raise GitHubProviderError("GITHUB_EXISTING_PROTECTION_UNSAFE_REQUIRES_MANUAL_REVIEW")
        if "test" not in _contexts(protection):
            try:
                result = api.post(
                    "/branches/main/protection/required_status_checks/contexts",
                    {"contexts": ["test"]},
                )
            except GitHubProviderError as exc:
                if str(exc) != "GITHUB_TRANSPORT_UNKNOWN":
                    raise
                _readback_after_unknown(
                    api,
                    lambda data: "test" in _contexts(data),
                    "GITHUB_TEST_CONTEXT_UNKNOWN_NOT_APPLIED",
                    "GITHUB_TEST_CONTEXT_PARTIAL_OR_AMBIGUOUS",
                )
            else:
                if result.status == 403:
                    raise GitHubProviderError("GITHUB_BRANCH_PROTECTION_ADMIN_PERMISSION_REQUIRED")
                if result.status != 200:
                    raise GitHubProviderError("GITHUB_TEST_CONTEXT_ADD_REJECTED")
            protection = _read_protection(api)
            if "test" not in _contexts(protection):
                raise GitHubProviderError("GITHUB_TEST_CONTEXT_POSTREADBACK_MISMATCH")
        if (protection.get("required_status_checks") or {}).get("strict") is not True:
            try:
                result = api.patch(
                    "/branches/main/protection/required_status_checks",
                    {"strict": True},
                )
            except GitHubProviderError as exc:
                if str(exc) != "GITHUB_TRANSPORT_UNKNOWN":
                    raise
                _readback_after_unknown(
                    api,
                    lambda data: (data.get("required_status_checks") or {}).get("strict") is True,
                    "GITHUB_STRICT_STATUS_UNKNOWN_NOT_APPLIED",
                    "GITHUB_STRICT_STATUS_PARTIAL_OR_AMBIGUOUS",
                )
            else:
                if result.status == 403:
                    raise GitHubProviderError("GITHUB_BRANCH_PROTECTION_ADMIN_PERMISSION_REQUIRED")
                if result.status != 200:
                    raise GitHubProviderError("GITHUB_STRICT_STATUS_UPDATE_REJECTED")
            protection = _read_protection(api)
        if not _flag(protection, "enforce_admins"):
            try:
                result = api.post("/branches/main/protection/enforce_admins")
            except GitHubProviderError as exc:
                if str(exc) != "GITHUB_TRANSPORT_UNKNOWN":
                    raise
                _readback_after_unknown(
                    api,
                    lambda data: _flag(data, "enforce_admins"),
                    "GITHUB_ADMIN_ENFORCEMENT_UNKNOWN_NOT_APPLIED",
                    "GITHUB_ADMIN_ENFORCEMENT_PARTIAL_OR_AMBIGUOUS",
                )
            else:
                if result.status == 403:
                    raise GitHubProviderError("GITHUB_BRANCH_PROTECTION_ADMIN_PERMISSION_REQUIRED")
                if result.status != 200:
                    raise GitHubProviderError("GITHUB_ADMIN_ENFORCEMENT_UPDATE_REJECTED")
        protection = _read_protection(api)
        if not _protection_safe(protection):
            raise GitHubProviderError("GITHUB_BRANCH_PROTECTION_POSTREADBACK_MISMATCH")
    else:
        raise GitHubProviderError("GITHUB_BRANCH_PROTECTION_READBACK_FAILED")
    state = read_state(api, repository, expected)
    write_evidence(state)
    return state


def bootstrap(api: Any, repository: str, expected: str, poll_seconds: int = 120) -> dict[str, Any]:
    if not getattr(api, "token", None):
        raise GitHubProviderError("GITHUB_WRITE_TOKEN_REQUIRED")
    repo = _require_ok(api.get(""), "GITHUB_REPOSITORY_READBACK_FAILED")
    if repo.get("full_name") != repository or repo.get("private") is not False or repo.get("default_branch") != "main":
        raise GitHubProviderError("GITHUB_REPOSITORY_IDENTITY_MISMATCH")
    branch = _require_ok(api.get("/branches/main"), "GITHUB_MAIN_READBACK_FAILED")
    before = str(((branch.get("commit") or {}).get("sha") or "")).lower()
    if before != expected:
        compare = _require_ok(api.get(f"/compare/{before}...{expected}"), "GITHUB_FAST_FORWARD_PROOF_FAILED")
        if compare.get("status") != "ahead" or int(compare.get("behind_by") or 0) != 0:
            raise GitHubProviderError("GITHUB_NON_FAST_FORWARD_FORBIDDEN")
        protection = api.get("/branches/main/protection")
        if protection.status != 200:
            raise GitHubProviderError("GITHUB_BRANCH_PROTECTION_MISSING")
        result = api.patch("/git/refs/heads/main", {"sha": expected, "force": False})
        if result.status not in (200, 201):
            raise GitHubProviderError("GITHUB_MAIN_FAST_FORWARD_FAILED")
        after = _require_ok(api.get("/branches/main"), "GITHUB_MAIN_POST_READBACK_FAILED")
        if str(((after.get("commit") or {}).get("sha") or "")).lower() != expected:
            raise GitHubProviderError("GITHUB_MAIN_POST_READBACK_MISMATCH")
    deadline = time.time() + poll_seconds
    while True:
        try:
            state = read_state(api, repository, expected)
            write_evidence(state)
            return state
        except GitHubProviderError as exc:
            if str(exc) not in {"GITHUB_EXACT_HEAD_CI_MISSING", "GITHUB_REQUIRED_TEST_CONTEXT_MISSING"} or time.time() >= deadline:
                raise
            time.sleep(5)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["readback", "bootstrap", "protect"])
    args = parser.parse_args(argv)
    try:
        repo, expected = env_target()
        require_local_identity(repo, expected)
        token = os.environ.get("FARE_GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
        api = GitHubApi(repo, token)
        if args.action == "readback":
            state = read_state(api, repo, expected)
            write_evidence(state)
        elif args.action == "protect":
            state = ensure_protection(api, repo, expected)
        else:
            state = bootstrap(api, repo, expected)
        print(json.dumps(state, sort_keys=True))
        return 0
    except GitHubProviderError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
