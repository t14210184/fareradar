from __future__ import annotations

import importlib.util
import pathlib
import sys
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location("access_review_runtime", ROOT / "scripts/access_review_runtime.py")
mod = importlib.util.module_from_spec(spec)
assert spec.loader
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)

HEAD = "a" * 40

class Result:
    def __init__(self, data, status=200):
        self.data = data
        self.status = status

class Transport:
    def __init__(self, data):
        self.data = data
    def health(self):
        return Result(self.data)

def test_accepts_current_deployment_mode_health_contract():
    data = {"spec":"1.3","deployment_mode":"SHADOW_ACCEPTANCE","commit_sha":HEAD}
    assert mod.verify_health_compat(Transport(data), HEAD) == data

def test_accepts_legacy_mode_alias_but_fails_wrong_identity():
    data = {"spec":"1.3","mode":"PRODUCTION","commit_sha":HEAD}
    assert mod.verify_health_compat(Transport(data), HEAD) == data
    with pytest.raises(mod.client.AccessReviewError):
        mod.verify_health_compat(Transport({**data,"commit_sha":"b"*40}), HEAD)
