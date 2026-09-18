from __future__ import annotations

import importlib.util
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location("d1_recovery", ROOT / "scripts/d1_recovery.py")
mod = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(mod)


def test_destructive_sql_classifier_blocks_same_release_cleanup():
    assert mod.sql_is_destructive("DROP TABLE legacy_offers;")
    assert mod.sql_is_destructive("ALTER TABLE offers DROP COLUMN obsolete;")
    assert mod.sql_is_destructive("ALTER TABLE offers RENAME COLUMN old_name TO new_name;")
    assert mod.sql_is_destructive("ALTER TABLE offers RENAME TO offers_v2;")


def test_expand_only_sql_remains_allowed():
    assert not mod.sql_is_destructive("CREATE TABLE IF NOT EXISTS new_table (id TEXT PRIMARY KEY);")
    assert not mod.sql_is_destructive("ALTER TABLE offers ADD COLUMN new_field TEXT;")
    assert not mod.sql_is_destructive("CREATE INDEX IF NOT EXISTS idx_offers_price ON offers(price);")


def test_pending_migrations_require_exact_prefix():
    expected = ["0001.sql", "0002.sql", "0003.sql"]
    assert mod.pending_migration_names(["0001.sql"], expected) == ["0002.sql", "0003.sql"]
    with pytest.raises(mod.D1RecoveryError, match="D1_MIGRATION_HISTORY_DRIFT"):
        mod.pending_migration_names(["0002.sql"], expected)


def test_recovery_manifest_preserves_worker_d1_boundary():
    doc = mod.recovery_manifest(
        database_id="db-id",
        before=["0001.sql"],
        pending=["0002.sql"],
        bookmark="00000006-00000002-00004e2f-0a83ea2fceebc654",
        after=["0001.sql", "0002.sql"],
    )
    assert doc["restore_policy"] == "HUMAN_GATE_ONLY_NEVER_AUTOMATIC"
    assert doc["worker_rollback_changes_d1"] is False
    assert doc["pre_migration_bookmark"].startswith("00000006-")
