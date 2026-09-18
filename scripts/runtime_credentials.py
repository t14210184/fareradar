from __future__ import annotations

import contextlib
import datetime as dt
import json
import os
import pathlib
import tempfile
from dataclasses import dataclass
from typing import Any, Iterator

import cloudflare_provider as cf

SHADOW_PATHS = [
    "/shadow/reviews",
    "/shadow/reviews/readback",
    "/shadow/acceptance/readback",
]
ACCESS_PATHS = [
    "/audit/evidence",
    "/audit/evidence/readback",
    "/sources/onboarding/review",
    "/providers/access/review",
    "/access/reviews/readback",
]


class RuntimeCredentialError(RuntimeError):
    pass


@dataclass(frozen=True)
class ReviewerCredential:
    key_id: str
    role: str
    secret_slot: str
    secret: str
    allowed_paths: tuple[str, ...]


@dataclass(frozen=True)
class RuntimeCredentialConfig:
    worker_token: str
    hmac_secrets_json: str
    hmac_secrets: dict[str, str]
    shadow: ReviewerCredential
    access: ReviewerCredential


def _required(env: dict[str, str], name: str) -> str:
    value = env.get(name, "")
    if not isinstance(value, str) or not value:
        raise RuntimeCredentialError(f"{name}_REQUIRED")
    return value


def load_config(env: dict[str, str] | None = None) -> RuntimeCredentialConfig:
    source = dict(os.environ if env is None else env)
    worker_token = _required(source, "FARE_WORKER_TOKEN")
    if len(worker_token) < 16:
        raise RuntimeCredentialError("FARE_WORKER_TOKEN_TOO_SHORT")

    raw_hmac = _required(source, "FARE_INGEST_HMAC_SECRETS")
    try:
        parsed = json.loads(raw_hmac)
    except json.JSONDecodeError as exc:
        raise RuntimeCredentialError("FARE_INGEST_HMAC_SECRETS_INVALID_JSON") from exc
    if (
        not isinstance(parsed, dict)
        or not parsed
        or any(
            not isinstance(slot, str)
            or not slot
            or not isinstance(secret, str)
            or len(secret) < 16
            for slot, secret in parsed.items()
        )
    ):
        raise RuntimeCredentialError("FARE_INGEST_HMAC_SECRETS_INVALID")

    shadow = ReviewerCredential(
        key_id=_required(source, "FARE_SHADOW_REVIEWER_KEY_ID"),
        role="SHADOW_REVIEWER",
        secret_slot=_required(source, "FARE_SHADOW_REVIEWER_SECRET_SLOT"),
        secret=_required(source, "FARE_SHADOW_REVIEWER_SECRET"),
        allowed_paths=tuple(SHADOW_PATHS),
    )
    access = ReviewerCredential(
        key_id=_required(source, "FARE_ACCESS_REVIEWER_KEY_ID"),
        role="ACCESS_REVIEWER",
        secret_slot=_required(source, "FARE_ACCESS_REVIEWER_SECRET_SLOT"),
        secret=_required(source, "FARE_ACCESS_REVIEWER_SECRET"),
        allowed_paths=tuple(ACCESS_PATHS),
    )
    if len(shadow.secret) < 16 or len(access.secret) < 16:
        raise RuntimeCredentialError("REVIEWER_SECRET_TOO_SHORT")
    if shadow.key_id == access.key_id:
        raise RuntimeCredentialError("REVIEWER_KEY_IDS_MUST_DIFFER")
    if shadow.secret_slot == access.secret_slot:
        raise RuntimeCredentialError("REVIEWER_SECRET_SLOTS_MUST_DIFFER")
    if shadow.secret == access.secret:
        raise RuntimeCredentialError("REVIEWER_SECRETS_MUST_DIFFER")
    if parsed.get(shadow.secret_slot) != shadow.secret:
        raise RuntimeCredentialError("SHADOW_REVIEWER_SECRET_SLOT_MISMATCH")
    if parsed.get(access.secret_slot) != access.secret:
        raise RuntimeCredentialError("ACCESS_REVIEWER_SECRET_SLOT_MISMATCH")

    canonical = json.dumps(parsed, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return RuntimeCredentialConfig(
        worker_token=worker_token,
        hmac_secrets_json=canonical,
        hmac_secrets=dict(parsed),
        shadow=shadow,
        access=access,
    )


def _sql_literal(value: str | None) -> str:
    if value is None:
        return "NULL"
    return "'" + value.replace("'", "''") + "'"


def _reviewer_rows(api: Any, database_id: str, key_id: str) -> list[dict[str, Any]]:
    sql = (
        "SELECT key_id,role,source_id,agency_id,provider_id,secret_slot,"
        "allowed_paths_json,enabled,not_before,expires_at "
        "FROM ingest_auth_keys WHERE key_id=" + _sql_literal(key_id)
    )
    return cf._query_rows(api, database_id, sql)


def _row_matches(row: dict[str, Any], credential: ReviewerCredential) -> bool:
    try:
        paths = json.loads(str(row.get("allowed_paths_json") or ""))
    except json.JSONDecodeError:
        return False
    return bool(
        row.get("key_id") == credential.key_id
        and row.get("role") == credential.role
        and row.get("source_id") is None
        and row.get("agency_id") is None
        and row.get("provider_id") is None
        and row.get("secret_slot") == credential.secret_slot
        and paths == list(credential.allowed_paths)
        and int(row.get("enabled") or 0) == 1
        and row.get("not_before") is None
        and row.get("expires_at") is None
    )


def _insert_reviewer(api: Any, database_id: str, credential: ReviewerCredential, created_at: str) -> None:
    paths = json.dumps(list(credential.allowed_paths), separators=(",", ":"))
    sql = (
        "INSERT INTO ingest_auth_keys("
        "key_id,role,source_id,agency_id,provider_id,secret_slot,"
        "allowed_paths_json,enabled,not_before,expires_at,created_at"
        ") VALUES("
        + ",".join([
            _sql_literal(credential.key_id),
            _sql_literal(credential.role),
            "NULL",
            "NULL",
            "NULL",
            _sql_literal(credential.secret_slot),
            _sql_literal(paths),
            "1",
            "NULL",
            "NULL",
            _sql_literal(created_at),
        ])
        + ")"
    )
    cf._query_rows(api, database_id, sql)


def ensure_reviewer_auth_keys(
    api: Any,
    database_id: str,
    config: RuntimeCredentialConfig,
    *,
    now: dt.datetime | None = None,
) -> dict[str, str]:
    observed: dict[str, str] = {}
    created_at = (now or dt.datetime.now(dt.timezone.utc)).isoformat().replace("+00:00", "Z")
    for credential in (config.shadow, config.access):
        before = _reviewer_rows(api, database_id, credential.key_id)
        if before:
            if len(before) != 1 or not _row_matches(before[0], credential):
                raise RuntimeCredentialError(f"REVIEWER_AUTH_KEY_CONFLICT:{credential.key_id}")
            observed[credential.key_id] = "EXACT_EXISTING"
            continue

        mutation_unknown = False
        try:
            _insert_reviewer(api, database_id, credential, created_at)
        except cf.CloudflareProviderError as exc:
            if str(exc) != "CLOUDFLARE_TRANSPORT_UNKNOWN":
                raise RuntimeCredentialError(
                    f"REVIEWER_AUTH_KEY_INSERT_FAILED:{credential.key_id}:{exc}"
                ) from exc
            mutation_unknown = True

        after = _reviewer_rows(api, database_id, credential.key_id)
        if len(after) == 1 and _row_matches(after[0], credential):
            observed[credential.key_id] = (
                "EXACT_AFTER_UNKNOWN" if mutation_unknown else "EXACT_CREATED"
            )
            continue
        if not after:
            code = (
                "REVIEWER_AUTH_KEY_UNKNOWN_NOT_APPLIED"
                if mutation_unknown
                else "REVIEWER_AUTH_KEY_POSTREADBACK_MISSING"
            )
            raise RuntimeCredentialError(f"{code}:{credential.key_id}")
        raise RuntimeCredentialError(f"REVIEWER_AUTH_KEY_PARTIAL_OR_AMBIGUOUS:{credential.key_id}")
    return observed


@contextlib.contextmanager
def secret_file(config: RuntimeCredentialConfig) -> Iterator[pathlib.Path]:
    fd, raw_path = tempfile.mkstemp(prefix="fare-radar-secrets-", suffix=".json")
    path = pathlib.Path(raw_path)
    try:
        os.fchmod(fd, 0o600)
        payload = {
            "WORKER_TOKEN": config.worker_token,
            "INGEST_HMAC_SECRETS": config.hmac_secrets_json,
        }
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))
            handle.write("\n")
        yield path
    finally:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
