from __future__ import annotations

import datetime as dt
import json
import pathlib
import re
from typing import Any

import cloudflare_provider as cf

ROOT = pathlib.Path(__file__).resolve().parents[1]
BOOKMARK_RE = re.compile(r"^[0-9a-fA-F-]{16,}$")
DESTRUCTIVE_PATTERNS = (
    re.compile(r"\bDROP\s+TABLE\b", re.I),
    re.compile(r"\bDROP\s+COLUMN\b", re.I),
    re.compile(r"\bALTER\s+TABLE\b[^;]*\bRENAME\s+(?:TO|COLUMN)\b", re.I | re.S),
)


class D1RecoveryError(RuntimeError):
    pass


def current_bookmark(api: Any, database_id: str) -> str:
    result = cf._result(
        api.get(f"/d1/database/{database_id}/time_travel/bookmark"),
        "D1_TIME_TRAVEL_BOOKMARK_READBACK_FAILED",
    )
    bookmark = str((result or {}).get("bookmark") or "") if isinstance(result, dict) else ""
    if not BOOKMARK_RE.fullmatch(bookmark):
        raise D1RecoveryError("D1_TIME_TRAVEL_BOOKMARK_INVALID")
    return bookmark


def pending_migration_names(current: list[str], expected: list[str]) -> list[str]:
    if current != expected[: len(current)]:
        raise D1RecoveryError("D1_MIGRATION_HISTORY_DRIFT")
    return expected[len(current):]


def migration_is_destructive(path: pathlib.Path) -> bool:
    text = path.read_text(encoding="utf-8")
    return any(pattern.search(text) for pattern in DESTRUCTIVE_PATTERNS)


def require_expand_only(pending: list[str]) -> None:
    destructive = [name for name in pending if migration_is_destructive(ROOT / "migrations" / name)]
    if destructive:
        raise D1RecoveryError("D1_DESTRUCTIVE_MIGRATION_BLOCKED:" + ",".join(destructive))


def recovery_manifest(*, database_id: str, before: list[str], pending: list[str], bookmark: str, after: list[str] | None = None) -> dict:
    return {
        "schema_version": 1,
        "kind": "d1-migration-recovery",
        "database_id": database_id,
        "observed_at": dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z"),
        "pre_migration_bookmark": bookmark,
        "before_migrations": list(before),
        "pending_migrations": list(pending),
        "after_migrations": list(after) if after is not None else None,
        "restore_policy": "HUMAN_GATE_ONLY_NEVER_AUTOMATIC",
        "worker_rollback_changes_d1": False,
    }


def write_manifest(doc: dict) -> pathlib.Path:
    directory = cf.evidence_dir()
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "d1-migration-recovery.json"
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path
