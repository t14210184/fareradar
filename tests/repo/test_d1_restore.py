from __future__ import annotations

import importlib.util
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location("d1_restore", ROOT / "scripts/d1_restore.py")
mod = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(mod)

DB = "11111111-2222-3333-4444-555555555555"
BOOKMARK = "00000006-00000002-00004e2f-0a83ea2fceebc654"


def envelope(result):
    return mod.cf.Response(200, {"success": True, "result": result})


class Api:
    def __init__(self):
        self.restore_calls = []
    def get(self, path):
        if path == f"/d1/database/{DB}":
            return envelope({"uuid": DB, "name": "fare-radar-production"})
        if path == f"/d1/database/{DB}/time_travel/bookmark":
            return envelope({"bookmark": BOOKMARK})
        raise AssertionError(path)
    def post(self, path, payload):
        self.restore_calls.append((path, payload))
        if path == f"/d1/database/{DB}/time_travel/restore":
            return envelope({"bookmark": BOOKMARK})
        raise AssertionError(path)


def test_restore_defaults_to_read_only_plan():
    api = Api()
    result = mod.restore(api, database_id=DB, bookmark=BOOKMARK, approved_bookmark="", execute=False)
    assert result["mode"] == "PLAN_ONLY"
    assert result["human_gate_required"] is True
    assert api.restore_calls == []


def test_restore_execute_requires_exact_human_approved_bookmark():
    api = Api()
    with pytest.raises(mod.D1RestoreError, match="D1_RESTORE_HUMAN_APPROVAL_REQUIRED"):
        mod.restore(api, database_id=DB, bookmark=BOOKMARK, approved_bookmark="", execute=True)
    assert api.restore_calls == []


def test_restore_dispatches_once_after_exact_approval_and_readback():
    api = Api()
    result = mod.restore(api, database_id=DB, bookmark=BOOKMARK, approved_bookmark=BOOKMARK, execute=True)
    assert result["mode"] == "RESTORED"
    assert len(api.restore_calls) == 1
    assert api.restore_calls[0][1] == {"bookmark": BOOKMARK}
