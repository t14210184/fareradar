from __future__ import annotations

import datetime as dt
import json
import os
import pathlib
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]
EVIDENCE_DIR = ROOT / "evidence" / "provider"
REQUIRED_SECRETS = {"WORKER_TOKEN", "INGEST_HMAC_SECRETS"}
ALLOWED_MODES = {"SHADOW_ACCEPTANCE", "PRODUCTION"}

class CloudflareProviderError(RuntimeError):
    pass

@dataclass
class Response:
    status: int
    data: Any

class CloudflareApi:
    def __init__(self, account_id: str, token: str, timeout: float = 20.0):
        self.account_id = account_id
        self.token = token
        self.timeout = timeout
        self.base = f"https://api.cloudflare.com/client/v4/accounts/{account_id}"

    def request(self, method: str, path: str, payload: Any | None = None) -> Response:
        body = None if payload is None else json.dumps(payload, separators=(",", ":")).encode()
        headers = {"authorization": f"Bearer {self.token}", "accept": "application/json", "user-agent": "fare-radar-v1.3"}
        if body is not None:
            headers["content-type"] = "application/json"
        req = urllib.request.Request(self.base + path, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                raw = r.read().decode()
                return Response(r.status, json.loads(raw) if raw else None)
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode(errors="replace")
            try:
                data = json.loads(raw) if raw else None
            except json.JSONDecodeError:
                data = {"raw": raw}
            return Response(exc.code, data)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise CloudflareProviderError("CLOUDFLARE_TRANSPORT_UNKNOWN") from exc

    def get(self, path: str) -> Response:
        return self.request("GET", path)

    def post(self, path: str, payload: Any) -> Response:
        return self.request("POST", path, payload)


def _result(response: Response, code: str) -> Any:
    if response.status != 200 or not isinstance(response.data, dict) or response.data.get("success") is not True:
        raise CloudflareProviderError(code)
    return response.data.get("result")


def _query_rows(api: Any, database_id: str, sql: str) -> list[dict[str, Any]]:
    result = _result(api.post(f"/d1/database/{database_id}/query", {"sql": sql}), "D1_QUERY_READBACK_FAILED")
    blocks = result if isinstance(result, list) else [result]
    rows: list[dict[str, Any]] = []
    for block in blocks:
        if isinstance(block, dict):
            values = block.get("results") or []
            rows.extend(x for x in values if isinstance(x, dict))
    return rows


def _binding_value(bindings: list[dict[str, Any]], name: str) -> Any:
    for binding in bindings:
        if binding.get("name") == name:
            return binding.get("text", binding.get("value"))
    return None


def _d1_binding(bindings: list[dict[str, Any]], database_id: str) -> bool:
    for binding in bindings:
        if binding.get("name") != "DB":
            continue
        value = binding.get("id", binding.get("database_id", binding.get("namespace_id")))
        if str(value or "") == database_id and str(binding.get("type", "")).lower() in {"d1", "d1_database", "d1database"}:
            return True
    return False


def _deployment_versions(result: Any) -> tuple[str, list[dict[str, Any]]]:
    if isinstance(result, dict):
        deployments = result.get("deployments") or []
    else:
        deployments = result or []
    if not isinstance(deployments, list) or not deployments:
        raise CloudflareProviderError("WORKER_DEPLOYMENT_MISSING")
    deployment = deployments[0]
    if not isinstance(deployment, dict):
        raise CloudflareProviderError("WORKER_DEPLOYMENT_INVALID")
    versions = deployment.get("versions") or []
    if len(versions) != 1 or float(versions[0].get("percentage") or 0) != 100.0 or not versions[0].get("version_id"):
        raise CloudflareProviderError("WORKER_ACTIVE_VERSION_NOT_SINGLE_100_PERCENT")
    return str(deployment.get("id") or ""), versions


def _migration_names() -> list[str]:
    return sorted(p.name for p in (ROOT / "migrations").glob("*.sql"))


def _seed_ids(path: pathlib.Path, key: str) -> set[str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return {str(row[key]) for row in data if isinstance(row, dict) and row.get(key)}


def collect_readback(api: Any, *, account_id: str, database_id: str, worker_name: str, expected_head: str, expected_mode: str) -> dict[str, Any]:
    session_id = str(uuid.uuid4())
    observed_at = dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")
    if expected_mode not in ALLOWED_MODES:
        raise CloudflareProviderError("DEPLOYMENT_MODE_INVALID")

    db = _result(api.get(f"/d1/database/{database_id}"), "D1_DATABASE_READBACK_FAILED")
    if not isinstance(db, dict) or str(db.get("uuid", db.get("id", ""))) != database_id or db.get("name") != "fare-radar-production":
        raise CloudflareProviderError("D1_DATABASE_IDENTITY_MISMATCH")

    settings = _result(api.get(f"/workers/scripts/{worker_name}/settings"), "WORKER_SETTINGS_READBACK_FAILED")
    if not isinstance(settings, dict):
        raise CloudflareProviderError("WORKER_SETTINGS_INVALID")
    bindings = [x for x in (settings.get("bindings") or []) if isinstance(x, dict)]
    if not _d1_binding(bindings, database_id):
        raise CloudflareProviderError("WORKER_D1_BINDING_MISMATCH")
    if _binding_value(bindings, "FARE_COMMIT_SHA") != expected_head:
        raise CloudflareProviderError("WORKER_COMMIT_BINDING_MISMATCH")
    if _binding_value(bindings, "FARE_DEPLOYMENT_MODE") != expected_mode:
        raise CloudflareProviderError("WORKER_DEPLOYMENT_MODE_MISMATCH")
    if str(_binding_value(bindings, "ALLOW_LEGACY_INGEST_TOKEN") or "0") == "1":
        raise CloudflareProviderError("LEGACY_INGEST_AUTH_ENABLED")

    deployments = _result(api.get(f"/workers/scripts/{worker_name}/deployments"), "WORKER_DEPLOYMENTS_READBACK_FAILED")
    deployment_id, versions = _deployment_versions(deployments)
    version_id = str(versions[0]["version_id"])

    secrets_result = _result(api.get(f"/workers/scripts/{worker_name}/secrets"), "WORKER_SECRETS_READBACK_FAILED")
    secrets_list = secrets_result if isinstance(secrets_result, list) else (secrets_result or {}).get("secrets", []) if isinstance(secrets_result, dict) else []
    secret_names = {str(x.get("name")) for x in secrets_list if isinstance(x, dict) and x.get("name")}
    if not REQUIRED_SECRETS <= secret_names:
        raise CloudflareProviderError("REQUIRED_WORKER_SECRETS_MISSING")
    if "LEGACY_INGEST_TOKEN" in secret_names:
        raise CloudflareProviderError("LEGACY_INGEST_SECRET_PRESENT")

    migrations = [str(x.get("name")) for x in _query_rows(api, database_id, "SELECT name FROM d1_migrations ORDER BY id")]
    expected_migrations = _migration_names()
    if migrations != expected_migrations:
        raise CloudflareProviderError("D1_MIGRATION_SET_MISMATCH")

    source_ids = {str(x.get("source_id")) for x in _query_rows(api, database_id, "SELECT source_id FROM source_registry")}
    provider_ids = {str(x.get("provider_id")) for x in _query_rows(api, database_id, "SELECT provider_id FROM provider_access_registry")}
    if not _seed_ids(ROOT / "config" / "sources.seed.json", "source_id") <= source_ids:
        raise CloudflareProviderError("SOURCE_BASELINE_SEEDS_MISSING")
    if not _seed_ids(ROOT / "config" / "providers.seed.json", "provider_id") <= provider_ids:
        raise CloudflareProviderError("PROVIDER_BASELINE_SEEDS_MISSING")

    missing_source_reviews = _query_rows(api, database_id, """
      SELECT s.source_id FROM source_registry s
      WHERE s.lifecycle_state='ENABLED' AND s.kill_switch=0 AND NOT EXISTS (
        SELECT 1 FROM source_onboarding_reviews r
        WHERE r.source_id=s.source_id AND r.target_state='ENABLED'
          AND r.terms_snapshot_at=s.terms_snapshot_at
          AND r.reviewer_key_id IS NOT NULL AND r.human_review_sha256 IS NOT NULL
      ) ORDER BY s.source_id
    """)
    if missing_source_reviews:
        raise CloudflareProviderError("DISPATCHABLE_SOURCE_REVIEW_MISSING")

    missing_provider_reviews = _query_rows(api, database_id, """
      SELECT p.provider_id FROM provider_access_registry p
      WHERE p.connector_state='IMPLEMENTED' AND p.kill_switch_state='CLEAR' AND NOT EXISTS (
        SELECT 1 FROM provider_access_reviews r
        WHERE r.provider_id=p.provider_id
          AND r.access_basis=p.access_basis
          AND r.terms_snapshot_at=p.terms_snapshot_at
          AND r.rate_policy=p.rate_policy
          AND (r.look_to_book_budget IS p.look_to_book_budget OR r.look_to_book_budget=p.look_to_book_budget)
          AND r.reviewer_key_id IS NOT NULL AND r.human_review_sha256 IS NOT NULL
      ) ORDER BY p.provider_id
    """)
    if missing_provider_reviews:
        raise CloudflareProviderError("DISPATCHABLE_PROVIDER_REVIEW_MISSING")

    return {
        "readback_session_id": session_id,
        "observed_at": observed_at,
        "provider": "cloudflare",
        "account_id": account_id,
        "database_id": database_id,
        "database_name": "fare-radar-production",
        "worker_name": worker_name,
        "commit_sha": expected_head,
        "deployment_mode": expected_mode,
        "deployment_id": deployment_id,
        "version_id": version_id,
        "binding_verified": True,
        "migrations_verified": True,
        "baseline_seeds_verified": True,
        "dispatchable_reviews_verified": True,
        "secret_names": sorted(secret_names),
        "legacy_ingest_auth_enabled": False,
    }


def write_evidence(state: dict[str, Any]) -> None:
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    common = {"readback_session_id": state["readback_session_id"], "observed_at": state["observed_at"], "provider": "cloudflare"}
    payloads = {
        "cloudflare-auth.json": {**common, "auth_verified": True, "account_id": state["account_id"]},
        "d1-readback.json": {**common, "binding_verified": True, "database_id": state["database_id"], "commit_sha": state["commit_sha"], "migrations_verified": True, "baseline_seeds_verified": True, "dispatchable_reviews_verified": True},
        "worker-deploy.json": {**common, "deployed": True, "version_id": state["version_id"], "deployment_id": state["deployment_id"], "commit_sha": state["commit_sha"], "deployment_mode": state["deployment_mode"]},
        "production-secrets.json": {**common, "required_secrets_verified": True, "secret_names": state["secret_names"], "legacy_ingest_auth_enabled": False, "commit_sha": state["commit_sha"]},
        "cloudflare-readback.json": state,
    }
    for name, payload in payloads.items():
        (EVIDENCE_DIR / name).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    token = os.environ.get("CLOUDFLARE_API_TOKEN", "")
    account_id = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "")
    database_id = os.environ.get("FARE_D1_DATABASE_ID", "")
    worker_name = os.environ.get("FARE_CLOUDFLARE_WORKER_NAME", "fare-radar")
    expected_head = os.environ.get("FARE_COMMIT_SHA", "").lower()
    expected_mode = os.environ.get("FARE_DEPLOYMENT_MODE", "")
    if not token or not account_id or not database_id or len(expected_head) != 40:
        print(json.dumps({"ok": False, "error": "CLOUDFLARE_READBACK_ENV_INCOMPLETE"}, sort_keys=True))
        return 2
    try:
        state = collect_readback(CloudflareApi(account_id, token), account_id=account_id, database_id=database_id, worker_name=worker_name, expected_head=expected_head, expected_mode=expected_mode)
        write_evidence(state)
        print(json.dumps(state, sort_keys=True))
        return 0
    except CloudflareProviderError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, sort_keys=True))
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
