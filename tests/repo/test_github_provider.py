from __future__ import annotations

import importlib.util
import pathlib
import sys
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("github_provider", ROOT / "scripts/github_provider.py")
mod = importlib.util.module_from_spec(spec)
assert spec.loader
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)

HEAD = "b" * 40
BEFORE = "a" * 40
REPO = "owner/fare-radar"

class Api:
    def __init__(self, *, main=HEAD, contexts=("test",), compare_status="ahead", token="token"):
        self.main = main
        self.contexts = list(contexts)
        self.compare_status = compare_status
        self.token = token
        self.patches = []
    def get(self, path):
        if path == "":
            return mod.Response(200,{"id":123,"full_name":REPO,"private":False,"default_branch":"main"})
        if path == "/branches/main":
            return mod.Response(200,{"commit":{"sha":self.main}})
        if path.startswith("/actions/runs?"):
            return mod.Response(200,{"workflow_runs":[{"id":99,"run_number":4,"head_sha":HEAD,"path":".github/workflows/ci.yml","status":"completed","conclusion":"success"}]})
        if path == "/branches/main/protection":
            return mod.Response(200,{"required_status_checks":{"contexts":self.contexts,"checks":[]},"enforce_admins":{"enabled":True}})
        if path.startswith("/compare/"):
            return mod.Response(200,{"status":self.compare_status,"behind_by":0})
        raise AssertionError(path)
    def patch(self, path, payload):
        self.patches.append((path,payload))
        if path == "/git/refs/heads/main" and payload == {"sha":HEAD,"force":False}:
            self.main = HEAD
            return mod.Response(200,{"object":{"sha":HEAD}})
        return mod.Response(400,{})

def test_read_state_requires_exact_ci_and_test_context():
    state = mod.read_state(Api(), REPO, HEAD)
    assert state["commit_sha"] == HEAD
    assert state["ci_run_id"] == 99
    assert state["required_status_contexts"] == ["test"]
    with pytest.raises(mod.GitHubProviderError, match="GITHUB_REQUIRED_TEST_CONTEXT_MISSING"):
        mod.read_state(Api(contexts=("lint",)), REPO, HEAD)

def test_bootstrap_uses_non_force_fast_forward_and_same_source_readback(monkeypatch):
    api = Api(main=BEFORE)
    monkeypatch.setattr(mod, "write_evidence", lambda state: None)
    state = mod.bootstrap(api, REPO, HEAD, poll_seconds=0)
    assert state["commit_sha"] == HEAD
    assert api.patches == [("/git/refs/heads/main", {"sha":HEAD,"force":False})]

def test_bootstrap_refuses_divergence_and_missing_protection(monkeypatch):
    api = Api(main=BEFORE, compare_status="diverged")
    monkeypatch.setattr(mod, "write_evidence", lambda state: None)
    with pytest.raises(mod.GitHubProviderError, match="GITHUB_NON_FAST_FORWARD_FORBIDDEN"):
        mod.bootstrap(api, REPO, HEAD, poll_seconds=0)
    assert api.patches == []

    class NoProtection(Api):
        def get(self, path):
            if path == "/branches/main/protection": return mod.Response(404,{})
            return super().get(path)
    api2 = NoProtection(main=BEFORE)
    with pytest.raises(mod.GitHubProviderError, match="GITHUB_BRANCH_PROTECTION_MISSING"):
        mod.bootstrap(api2, REPO, HEAD, poll_seconds=0)
    assert api2.patches == []
