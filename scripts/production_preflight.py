from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import pathlib
import re
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[1]
PLACEHOLDERS = {"", "REPLACE_WITH_D1_DATABASE_ID", "TODO", "TBD"}
REQUIRED_WORKER_SECRETS = {"WORKER_TOKEN", "INGEST_HMAC_SECRETS"}
EXPECTED_COMPLEX_STRATEGIES = {"S09", "S11", "S12", "S14", "S15"}

BLOCKER_MANIFEST = {
    "LOCAL_CODE_GATES_NOT_READY": {
        "domain": "LOCAL_CODE",
        "authority": "CHAT_OR_OPERATOR",
        "requires_human_authority": False,
        "requires_provider": False,
        "provider": None,
        "next_action": "npm run gates:all",
    },
    "GITHUB_REMOTE_MISSING": {
        "domain": "LOCAL_CONFIGURATION",
        "authority": "REPOSITORY_OPERATOR",
        "requires_human_authority": False,
        "requires_provider": True,
        "provider": "github",
        "next_action": "configure exact GitHub origin and rerun npm run readback:github",
    },
    "GITHUB_PROVIDER_READBACK_MISSING": {
        "domain": "GITHUB_GOVERNANCE",
        "authority": "GITHUB_REPOSITORY_ADMIN",
        "requires_human_authority": True,
        "requires_provider": True,
        "provider": "github",
        "next_action": "npm run protect:github && npm run readback:github",
    },
    "D1_DATABASE_ID_MISSING": {
        "domain": "CLOUDFLARE_PROVISIONING",
        "authority": "CLOUDFLARE_ACCOUNT",
        "requires_human_authority": False,
        "requires_provider": True,
        "provider": "cloudflare",
        "next_action": "npm run provision:shadow",
    },
    "LEGACY_INGEST_AUTH_ENABLED": {
        "domain": "SECURITY_CONFIGURATION",
        "authority": "CHAT_OR_OPERATOR",
        "requires_human_authority": False,
        "requires_provider": False,
        "provider": None,
        "next_action": "disable legacy ingest auth and rerun npm run preflight",
    },
    "CLOUDFLARE_READBACK_SESSION_MISMATCH": {
        "domain": "CLOUDFLARE_READBACK",
        "authority": "CLOUDFLARE_ACCOUNT",
        "requires_human_authority": False,
        "requires_provider": True,
        "provider": "cloudflare",
        "next_action": "npm run readback:cloudflare",
    },
    "CLOUDFLARE_AUTH_READBACK_MISSING": {
        "domain": "CLOUDFLARE_READBACK",
        "authority": "CLOUDFLARE_ACCOUNT",
        "requires_human_authority": False,
        "requires_provider": True,
        "provider": "cloudflare",
        "next_action": "npm run readback:cloudflare",
    },
    "D1_PROVIDER_READBACK_MISSING": {
        "domain": "CLOUDFLARE_READBACK",
        "authority": "CLOUDFLARE_ACCOUNT",
        "requires_human_authority": False,
        "requires_provider": True,
        "provider": "cloudflare",
        "next_action": "npm run readback:cloudflare",
    },
    "WORKER_DEPLOY_READBACK_MISSING": {
        "domain": "CLOUDFLARE_WORKER",
        "authority": "CLOUDFLARE_ACCOUNT",
        "requires_human_authority": False,
        "requires_provider": True,
        "provider": "cloudflare",
        "next_action": "npm run deploy:shadow",
    },
    "PRODUCTION_SECRETS_READBACK_MISSING": {
        "domain": "CLOUDFLARE_SECRETS",
        "authority": "CLOUDFLARE_ACCOUNT",
        "requires_human_authority": False,
        "requires_provider": True,
        "provider": "cloudflare",
        "next_action": "npm run deploy:shadow && npm run readback:cloudflare",
    },
    "SHADOW_ACCEPTANCE_MISSING": {
        "domain": "SHADOW_ACCEPTANCE",
        "authority": "HUMAN_REVIEWER_AND_TIME",
        "requires_human_authority": True,
        "requires_provider": True,
        "provider": "cloudflare",
        "next_action": "npm run shadow:review and continue exact-head Shadow observation until all thresholds pass",
    },
    "PRODUCTION_ACTIVATION_REQUIRED": {
        "domain": "PRODUCTION_ACTIVATION",
        "authority": "HUMAN_RELEASE_APPROVER",
        "requires_human_authority": True,
        "requires_provider": True,
        "provider": "cloudflare",
        "next_action": "set exact FARE_PRODUCTION_HUMAN_APPROVED_HEAD then npm run deploy:production",
    },
}


def blocker_details(blockers):
    details = []
    for code in blockers:
        metadata = BLOCKER_MANIFEST.get(code)
        if metadata is None:
            raise RuntimeError(f"BLOCKER_MANIFEST_MISSING:{code}")
        details.append({"code": code, **metadata})
    return details


def evidence_root() -> pathlib.Path:
    raw = os.environ.get("FARE_EVIDENCE_ROOT", "")
    if not raw:
        return ROOT / "evidence"
    path = pathlib.Path(raw).expanduser()
    if not path.is_absolute():
        raise ValueError("FARE_EVIDENCE_ROOT_MUST_BE_ABSOLUTE")
    return path


def github_remote_ok(url: str | None):
    if not url:
        return False
    return bool(re.match(r"^(https://github\.com/|git@github\.com:|ssh://git@github\.com/)", url))


def load_json(path: pathlib.Path):
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def git_head():
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return None


def evidence_commit_ok(data, head=None):
    return bool(data and (data.get("commit_sha") == (head or git_head())))


def evidence_recent(data, max_hours=24, now=None):
    if not data or not data.get("observed_at"):
        return False
    try:
        seen = dt.datetime.fromisoformat(str(data["observed_at"]).replace("Z", "+00:00"))
        now = now or dt.datetime.now(dt.timezone.utc)
        return seen.tzinfo is not None and dt.timedelta(0) <= now - seen <= dt.timedelta(hours=max_hours)
    except Exception:
        return False


def _hash_paths(paths):
    h = hashlib.sha256()
    for path in sorted(paths, key=lambda p: p.as_posix()):
        rel = path.relative_to(ROOT).as_posix().encode()
        data = path.read_bytes()
        h.update(len(rel).to_bytes(4, "big"))
        h.update(rel)
        h.update(len(data).to_bytes(8, "big"))
        h.update(data)
    return h.hexdigest()


def _current_evidence_context(head):
    tests = subprocess.check_output(["git", "ls-files", "tests"], cwd=ROOT, text=True).splitlines()
    return {
        "commit_sha": head,
        "spec_sha256": hashlib.sha256((ROOT / "docs/SPEC_v1.3.md").read_bytes()).hexdigest(),
        "dependency_lock_sha256": _hash_paths([ROOT / "package-lock.json", ROOT / "requirements-dev.txt"]),
        "test_corpus_sha256": _hash_paths([ROOT / x for x in tests if (ROOT / x).is_file()]),
    }


def _spec_gate_mapping():
    text = (ROOT / "docs/SPEC_v1.3.md").read_text()
    match = re.search(r"## 43\.2 Gate-to-test executable mapping\n(.*?)(?:\n## 43\.3 )", text, re.S)
    if not match:
        return []
    rows = []
    for line in match.group(1).splitlines():
        row = re.match(r"\|\s*(PG\d{2})\s*\|\s*`([^`]+)`\s*\|\s*(.*?)\s*\|$", line)
        if row:
            rows.append((row.group(1), row.group(2), row.group(3)))
    return rows


def code_ready_from_evidence(data, head):
    if not head or not data or data.get("schema_version") != 2:
        return False
    if any(data.get(key) != value for key, value in _current_evidence_context(head).items()):
        return False
    summary = data.get("summary", {})
    gates = data.get("gates", [])
    mapping = _spec_gate_mapping()
    if len(mapping) != 37 or [x[0] for x in mapping] != [f"PG{i:02d}" for i in range(37)]:
        return False
    if not (
        summary.get("LOCAL_TEST_PASS") == 37
        and summary.get("LOCAL_TEST_FAIL") == 0
        and summary.get("EVIDENCE_INCOMPLETE") == 0
        and len(gates) == 37
    ):
        return False
    for gate, (gate_id, command, threshold) in zip(gates, mapping):
        if (
            gate.get("gate_id") != gate_id
            or gate.get("exact_command") != command
            or gate.get("expected_threshold") != threshold
            or gate.get("status") != "LOCAL_TEST_PASS"
            or gate.get("commit_sha") != head
        ):
            return False
        if not re.fullmatch(r"[0-9a-f]{64}", str(gate.get("report_sha256", ""))):
            return False
    full = data.get("full_suite", {})
    return (
        full.get("status") == "FULL_SUITE_PASS"
        and full.get("stage_count") == 5
        and full.get("file_count", 0) > 0
        and bool(re.fullmatch(r"[0-9a-f]{64}", str(full.get("report_sha256", ""))))
    )


def code_ready(head=None):
    head = head or git_head()
    return code_ready_from_evidence(load_json(evidence_root() / "gate-evidence-latest.json") or {}, head)


def d1_id():
    text = (ROOT / "wrangler.jsonc").read_text()
    match = re.search(r'"database_id"\s*:\s*"([^"]+)"', text)
    return match.group(1) if match else ""


def provider_evidence(name):
    return load_json(evidence_root() / "provider" / f"{name}.json")


def legacy_ingest_enabled():
    if os.environ.get("ALLOW_LEGACY_INGEST_TOKEN") == "1":
        return True
    try:
        text = (ROOT / "wrangler.jsonc").read_text()
    except Exception:
        return False
    return bool(re.search(r'"ALLOW_LEGACY_INGEST_TOKEN"\s*:\s*"?1"?', text))


def github_readback_ok(data, head):
    expected = os.environ.get("FARE_GITHUB_REPOSITORY")
    contexts = set(data.get("required_status_contexts") or []) if data else set()
    return bool(
        data
        and data.get("provider") == "github"
        and data.get("visibility") == "public"
        and data.get("default_branch") == "main"
        and data.get("ci_conclusion") == "success"
        and data.get("branch_protection_verified") is True
        and "test" in contexts
        and evidence_commit_ok(data, head)
        and evidence_recent(data, 24)
        and (not expected or data.get("repository_full_name") == expected)
    )


def cloudflare_session_ok(*items):
    ids = [str(item.get("readback_session_id") or "") for item in items]
    return bool(items) and all(ids) and len(set(ids)) == 1


def auth_ok(data):
    return bool(data and data.get("provider") == "cloudflare" and data.get("auth_verified") is True and evidence_recent(data, 24))


def d1_readback_ok(data, head):
    return bool(
        data
        and data.get("provider") == "cloudflare"
        and data.get("binding_verified") is True
        and data.get("migrations_verified") is True
        and data.get("baseline_seeds_verified") is True
        and data.get("dispatchable_reviews_verified") is True
        and data.get("database_id") == d1_id()
        and evidence_commit_ok(data, head)
        and evidence_recent(data, 24)
    )


def deploy_ok(data, head):
    return bool(
        data
        and data.get("provider") == "cloudflare"
        and data.get("deployed") is True
        and data.get("version_id")
        and data.get("deployment_mode") in {"SHADOW_ACCEPTANCE", "PRODUCTION"}
        and evidence_commit_ok(data, head)
        and evidence_recent(data, 24)
    )


def production_deploy_ok(data, head):
    return bool(deploy_ok(data, head) and data.get("deployment_mode") == "PRODUCTION")


def secrets_ok(data, head):
    names = set(data.get("secret_names") or []) if data else set()
    return bool(
        data
        and data.get("provider") == "cloudflare"
        and data.get("required_secrets_verified") is True
        and REQUIRED_WORKER_SECRETS <= names
        and data.get("legacy_ingest_auth_enabled") is False
        and evidence_commit_ok(data, head)
        and evidence_recent(data, 24)
    )


def shadow_ok(head=None):
    data = load_json(evidence_root() / "shadow-acceptance.json") or {}
    head = head or git_head()
    coverage = set(data.get("complex_strategy_coverage") or [])
    missing = data.get("complex_strategy_missing")
    return bool(
        data.get("pass") is True
        and data.get("commit_sha") == head
        and data.get("deployment_mode") == "SHADOW_ACCEPTANCE"
        and data.get("shadow_days", 0) >= 14
        and data.get("labeled_candidates", 0) >= 150
        and data.get("labeled_complex_candidates", 0) >= 30
        and data.get("labeled_source_discovery_events", 0) >= 30
        and data.get("labeled_agency_clearance_events", 0) >= 10
        and EXPECTED_COMPLEX_STRATEGIES <= coverage
        and missing == []
        and data.get("false_actionable_complex", 1) == 0
        and data.get("safety_critical_errors", 1) == 0
    )


def git_remote():
    try:
        return subprocess.check_output(["git", "remote", "get-url", "origin"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return None


def evaluate(remote=None):
    blockers = []
    head = git_head()
    if not code_ready(head):
        blockers.append("LOCAL_CODE_GATES_NOT_READY")
    if not github_remote_ok(remote if remote is not None else git_remote()):
        blockers.append("GITHUB_REMOTE_MISSING")
    github = provider_evidence("github-readback") or {}
    if not github_readback_ok(github, head):
        blockers.append("GITHUB_PROVIDER_READBACK_MISSING")
    if d1_id() in PLACEHOLDERS:
        blockers.append("D1_DATABASE_ID_MISSING")
    if legacy_ingest_enabled():
        blockers.append("LEGACY_INGEST_AUTH_ENABLED")
    auth = provider_evidence("cloudflare-auth") or {}
    d1 = provider_evidence("d1-readback") or {}
    deploy = provider_evidence("worker-deploy") or {}
    secrets = provider_evidence("production-secrets") or {}
    if not cloudflare_session_ok(auth, d1, deploy, secrets):
        blockers.append("CLOUDFLARE_READBACK_SESSION_MISMATCH")
    if not auth_ok(auth):
        blockers.append("CLOUDFLARE_AUTH_READBACK_MISSING")
    if not d1_readback_ok(d1, head):
        blockers.append("D1_PROVIDER_READBACK_MISSING")
    if not deploy_ok(deploy, head):
        blockers.append("WORKER_DEPLOY_READBACK_MISSING")
    if not secrets_ok(secrets, head):
        blockers.append("PRODUCTION_SECRETS_READBACK_MISSING")
    if not shadow_ok(head):
        blockers.append("SHADOW_ACCEPTANCE_MISSING")
    if deploy_ok(deploy, head) and not production_deploy_ok(deploy, head):
        blockers.append("PRODUCTION_ACTIVATION_REQUIRED")
    return {"code_ready": code_ready(head), "production_ready": not blockers, "commit_sha": head, "blockers": blockers, "blocker_details": blocker_details(blockers)}


if __name__ == "__main__":
    print(json.dumps(evaluate(), ensure_ascii=False, indent=2))
