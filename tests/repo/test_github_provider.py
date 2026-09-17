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
    def __init__(
        self,
        *,
        main=HEAD,
        contexts=("test",),
        strict=True,
        enforce_admins=True,
        allow_force_pushes=False,
        allow_deletions=False,
        compare_status="ahead",
        token="token",
        protection_exists=True,
    ):
        self.main = main
        self.contexts = list(contexts)
        self.strict = strict
        self.enforce_admins = enforce_admins
        self.allow_force_pushes = allow_force_pushes
        self.allow_deletions = allow_deletions
        self.compare_status = compare_status
        self.token = token
        self.protection_exists = protection_exists
        self.patches = []
        self.posts = []
        self.puts = []

    def _protection(self):
        return {
            "required_status_checks": {"strict": self.strict, "contexts": list(self.contexts), "checks": []},
            "enforce_admins": {"enabled": self.enforce_admins},
            "allow_force_pushes": {"enabled": self.allow_force_pushes},
            "allow_deletions": {"enabled": self.allow_deletions},
            "required_pull_request_reviews": {"dismiss_stale_reviews": True},
            "marker": "preserve-me",
        }

    def get(self, path):
        if path == "":
            return mod.Response(200, {"id": 123, "full_name": REPO, "private": False, "default_branch": "main"})
        if path == "/branches/main":
            return mod.Response(200, {"commit": {"sha": self.main}})
        if path.startswith("/actions/runs?"):
            return mod.Response(
                200,
                {
                    "workflow_runs": [
                        {
                            "id": 99,
                            "run_number": 4,
                            "head_sha": HEAD,
                            "path": ".github/workflows/ci.yml",
                            "status": "completed",
                            "conclusion": "success",
                        }
                    ]
                },
            )
        if path == "/branches/main/protection":
            if not self.protection_exists:
                return mod.Response(404, {})
            return mod.Response(200, self._protection())
        if path.startswith("/compare/"):
            return mod.Response(200, {"status": self.compare_status, "behind_by": 0})
        raise AssertionError(path)

    def patch(self, path, payload):
        self.patches.append((path, payload))
        if path == "/git/refs/heads/main" and payload == {"sha": HEAD, "force": False}:
            self.main = HEAD
            return mod.Response(200, {"object": {"sha": HEAD}})
        if path == "/branches/main/protection/required_status_checks" and payload == {"strict": True}:
            self.strict = True
            return mod.Response(200, {"strict": True, "contexts": list(self.contexts)})
        return mod.Response(400, {})

    def post(self, path, payload=None):
        self.posts.append((path, payload))
        if path == "/branches/main/protection/required_status_checks/contexts" and payload == {"contexts": ["test"]}:
            if "test" not in self.contexts:
                self.contexts.append("test")
            return mod.Response(200, list(self.contexts))
        if path == "/branches/main/protection/enforce_admins" and payload is None:
            self.enforce_admins = True
            return mod.Response(200, {"enabled": True})
        return mod.Response(400, {})

    def put(self, path, payload):
        self.puts.append((path, payload))
        if path != "/branches/main/protection":
            return mod.Response(400, {})
        self.protection_exists = True
        self.contexts = list((payload.get("required_status_checks") or {}).get("contexts") or [])
        self.strict = (payload.get("required_status_checks") or {}).get("strict") is True
        self.enforce_admins = payload.get("enforce_admins") is True
        self.allow_force_pushes = payload.get("allow_force_pushes") is True
        self.allow_deletions = payload.get("allow_deletions") is True
        return mod.Response(200, self._protection())


def test_read_state_requires_strict_safe_protection():
    state = mod.read_state(Api(), REPO, HEAD)
    assert state["commit_sha"] == HEAD
    assert state["ci_run_id"] == 99
    assert state["required_status_contexts"] == ["test"]
    assert state["required_status_strict"] is True
    assert state["admin_enforcement"] is True
    assert state["force_pushes_allowed"] is False
    assert state["branch_deletions_allowed"] is False

    with pytest.raises(mod.GitHubProviderError, match="GITHUB_REQUIRED_TEST_CONTEXT_MISSING"):
        mod.read_state(Api(contexts=("lint",)), REPO, HEAD)
    with pytest.raises(mod.GitHubProviderError, match="GITHUB_REQUIRED_STATUS_STRICT_MISSING"):
        mod.read_state(Api(strict=False), REPO, HEAD)
    with pytest.raises(mod.GitHubProviderError, match="GITHUB_ADMIN_ENFORCEMENT_MISSING"):
        mod.read_state(Api(enforce_admins=False), REPO, HEAD)
    with pytest.raises(mod.GitHubProviderError, match="GITHUB_FORCE_PUSH_ALLOWED"):
        mod.read_state(Api(allow_force_pushes=True), REPO, HEAD)
    with pytest.raises(mod.GitHubProviderError, match="GITHUB_BRANCH_DELETION_ALLOWED"):
        mod.read_state(Api(allow_deletions=True), REPO, HEAD)


def test_protect_creates_safe_baseline_when_missing(monkeypatch):
    api = Api(protection_exists=False)
    monkeypatch.setattr(mod, "write_evidence", lambda state: None)
    state = mod.ensure_protection(api, REPO, HEAD)
    assert state["branch_protection_verified"] is True
    assert len(api.puts) == 1
    path, payload = api.puts[0]
    assert path == "/branches/main/protection"
    assert payload["required_status_checks"] == {"strict": True, "contexts": ["test"]}
    assert payload["enforce_admins"] is True
    assert payload["required_linear_history"] is True
    assert payload["allow_force_pushes"] is False
    assert payload["allow_deletions"] is False


def test_protect_existing_only_strengthens_scoped_subresources(monkeypatch):
    api = Api(contexts=("lint",), strict=False, enforce_admins=False)
    before = api._protection()["required_pull_request_reviews"].copy()
    monkeypatch.setattr(mod, "write_evidence", lambda state: None)
    state = mod.ensure_protection(api, REPO, HEAD)
    assert state["required_status_contexts"] == ["lint", "test"]
    assert api.puts == []
    assert api.posts == [
        ("/branches/main/protection/required_status_checks/contexts", {"contexts": ["test"]}),
        ("/branches/main/protection/enforce_admins", None),
    ]
    assert api.patches == [
        ("/branches/main/protection/required_status_checks", {"strict": True}),
    ]
    assert api._protection()["required_pull_request_reviews"] == before
    assert api._protection()["marker"] == "preserve-me"


def test_protect_unknown_create_uses_readback_without_resend(monkeypatch):
    class UnknownCreate(Api):
        def put(self, path, payload):
            response = super().put(path, payload)
            assert response.status == 200
            raise mod.GitHubProviderError("GITHUB_TRANSPORT_UNKNOWN")

    api = UnknownCreate(protection_exists=False)
    monkeypatch.setattr(mod, "write_evidence", lambda state: None)
    state = mod.ensure_protection(api, REPO, HEAD)
    assert state["branch_protection_verified"] is True
    assert len(api.puts) == 1


def test_protect_refuses_unsafe_existing_force_or_delete(monkeypatch):
    monkeypatch.setattr(mod, "write_evidence", lambda state: None)
    for api in (Api(allow_force_pushes=True), Api(allow_deletions=True)):
        with pytest.raises(mod.GitHubProviderError, match="GITHUB_EXISTING_PROTECTION_UNSAFE_REQUIRES_MANUAL_REVIEW"):
            mod.ensure_protection(api, REPO, HEAD)
        assert api.puts == []
        assert api.posts == []
        assert api.patches == []


def test_protect_requires_admin_token(monkeypatch):
    api = Api(token="")
    monkeypatch.setattr(mod, "write_evidence", lambda state: None)
    with pytest.raises(mod.GitHubProviderError, match="GITHUB_ADMIN_TOKEN_REQUIRED"):
        mod.ensure_protection(api, REPO, HEAD)


def test_bootstrap_uses_non_force_fast_forward_and_same_source_readback(monkeypatch):
    api = Api(main=BEFORE)
    monkeypatch.setattr(mod, "write_evidence", lambda state: None)
    state = mod.bootstrap(api, REPO, HEAD, poll_seconds=0)
    assert state["commit_sha"] == HEAD
    assert api.patches == [("/git/refs/heads/main", {"sha": HEAD, "force": False})]


def test_bootstrap_refuses_divergence_and_missing_protection(monkeypatch):
    api = Api(main=BEFORE, compare_status="diverged")
    monkeypatch.setattr(mod, "write_evidence", lambda state: None)
    with pytest.raises(mod.GitHubProviderError, match="GITHUB_NON_FAST_FORWARD_FORBIDDEN"):
        mod.bootstrap(api, REPO, HEAD, poll_seconds=0)
    assert api.patches == []

    api2 = Api(main=BEFORE, protection_exists=False)
    with pytest.raises(mod.GitHubProviderError, match="GITHUB_BRANCH_PROTECTION_MISSING"):
        mod.bootstrap(api2, REPO, HEAD, poll_seconds=0)
    assert api2.patches == []
