from __future__ import annotations

import importlib.util
import pathlib
import sys
from types import SimpleNamespace

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location("provision_shadow", ROOT / "scripts/provision_shadow.py")
mod = importlib.util.module_from_spec(spec)
assert spec.loader
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)

DB = "11111111-2222-3333-4444-555555555555"
HEAD = "a" * 40
REPO = "acme/fare-radar"


def envelope(result, status=200):
    return mod.cf.Response(status, {"success": True, "errors": [], "messages": [], "result": result})


class CfApi:
    def __init__(self):
        self.databases: list[dict] = []
        self.create_calls = 0
        self.create_unknown = False
        self.create_not_applied = False
        self.migrations: list[str] = []
        self.sources: set[str] = set()
        self.providers: set[str] = set()
        self.bookmark = "00000006-00000002-00004e2f-0a83ea2fceebc654"
    def get(self, path):
        if path.startswith("/d1/database?"):
            return envelope(list(self.databases))
        if path == f"/d1/database/{DB}":
            return envelope({"uuid": DB, "name": mod.DB_NAME})
        if path == f"/d1/database/{DB}/time_travel/bookmark":
            return envelope({"bookmark": self.bookmark})
        raise AssertionError(path)
    def post(self, path, payload):
        if path == "/d1/database":
            self.create_calls += 1
            if not self.create_not_applied:
                row = {"uuid": DB, "name": mod.DB_NAME}
                if not self.databases:
                    self.databases.append(row)
            if self.create_unknown:
                raise mod.cf.CloudflareProviderError("CLOUDFLARE_TRANSPORT_UNKNOWN")
            if self.create_not_applied:
                return mod.cf.Response(500, {"success": False, "result": None})
            return envelope(self.databases[0])
        if path == f"/d1/database/{DB}/query":
            sql = payload["sql"]
            if "sqlite_master" in sql:
                rows = [{"name": "d1_migrations"}] if self.migrations else []
            elif "FROM d1_migrations" in sql:
                rows = [{"name": item} for item in self.migrations]
            elif "SELECT source_id FROM source_registry" in sql:
                rows = [{"source_id": item} for item in sorted(self.sources)]
            elif "SELECT provider_id FROM provider_access_registry" in sql:
                rows = [{"provider_id": item} for item in sorted(self.providers)]
            else:
                raise AssertionError(sql)
            return envelope([{"success": True, "results": rows}])
        raise AssertionError(path)


class GhApi:
    def __init__(self):
        self.token = "token"
        self.branches = {"main": HEAD}
        self.runs = [{"id": 7, "run_number": 3, "head_sha": HEAD, "head_branch": "main", "path": ".github/workflows/ci.yml", "status": "completed", "conclusion": "success"}]
    def get(self, path):
        if path == "":
            return mod.gh.Response(200, {"full_name": REPO, "private": False, "default_branch": "main"})
        if path == "/branches/main":
            return mod.gh.Response(200, {"commit": {"sha": self.branches["main"]}})
        if path.startswith("/branches/"):
            name = path.split("/branches/", 1)[1]
            if name not in self.branches:
                return mod.gh.Response(404, {"message": "Not Found"})
            return mod.gh.Response(200, {"commit": {"sha": self.branches[name]}})
        if path.startswith("/actions/runs?"):
            return mod.gh.Response(200, {"workflow_runs": list(self.runs)})
        raise AssertionError(path)


def test_d1_reuses_unique_exact_database_without_create():
    api = CfApi(); api.databases = [{"uuid": DB, "name": mod.DB_NAME}]
    identity = mod.ensure_d1(api)
    assert identity.database_id == DB and identity.reused is True
    assert api.create_calls == 0


def test_d1_unknown_create_is_reconciled_by_readback_without_resend():
    api = CfApi(); api.create_unknown = True
    identity = mod.ensure_d1(api)
    assert identity.database_id == DB and identity.reused is False
    assert api.create_calls == 1


def test_d1_rejected_create_with_absent_readback_is_not_resent():
    api = CfApi(); api.create_not_applied = True
    with pytest.raises(mod.ShadowProvisionError, match="D1_CREATE_NOT_APPLIED"):
        mod.ensure_d1(api)
    assert api.create_calls == 1


def test_migration_lost_response_accepts_exact_provider_readback(tmp_path, monkeypatch):
    api = CfApi(); expected = mod.cf._migration_names(); config = tmp_path / "wrangler.jsonc"; config.write_text("{}")
    captured=[]
    monkeypatch.setattr(mod.d1r, "write_manifest", lambda doc: captured.append(dict(doc)))
    calls=[]
    def runner(args, **kwargs):
        calls.append(args); api.migrations = list(expected); return SimpleNamespace(returncode=1, stdout="", stderr="lost")
    result = mod.ensure_migrations(api, DB, config, runner=runner)
    assert result == "readback_confirmed"
    assert len(calls) == 1
    assert captured[0]["pre_migration_bookmark"] == api.bookmark
    assert captured[0]["before_migrations"] == []
    assert captured[0]["pending_migrations"] == expected
    assert captured[-1]["after_migrations"] == expected


def test_migration_partial_state_is_ambiguous_not_retried(tmp_path, monkeypatch):
    api = CfApi(); expected = mod.cf._migration_names(); config = tmp_path / "wrangler.jsonc"; config.write_text("{}")
    monkeypatch.setattr(mod.d1r, "write_manifest", lambda doc: None)
    def runner(args, **kwargs):
        api.migrations = list(expected[:2]); return SimpleNamespace(returncode=1, stdout="", stderr="partial")
    with pytest.raises(mod.ShadowProvisionError, match="D1_MIGRATIONS_PARTIAL_OR_AMBIGUOUS"):
        mod.ensure_migrations(api, DB, config, runner=runner)


def test_seed_lost_response_accepts_complete_readback(tmp_path):
    api = CfApi(); api.migrations = mod.cf._migration_names(); config = tmp_path / "wrangler.jsonc"; config.write_text("{}")
    sources, providers = mod.baseline_expected(); calls=[]
    def runner(args, **kwargs):
        calls.append(args); api.sources = set(sources); api.providers = set(providers); return SimpleNamespace(returncode=1, stdout="", stderr="lost")
    result = mod.ensure_seed(api, DB, config, runner=runner)
    assert result == "readback_confirmed" and len(calls) == 1


def test_github_target_precheck_requires_main_exact_head_success():
    api = GhApi()
    got = mod.github_target_precheck(api, REPO, HEAD)
    assert got["ci_run_id"] == 7
    api.runs[0]["head_branch"] = "feature"
    with pytest.raises(mod.ShadowProvisionError, match="GITHUB_MAIN_EXACT_HEAD_CI_MISSING"):
        mod.github_target_precheck(api, REPO, HEAD)


def test_release_branch_unknown_push_is_readback_first():
    api = GhApi(); release = "b" * 40; branch = f"shadow-release-{release[:12]}"; calls=[]
    def runner(args, **kwargs):
        calls.append(args); api.branches[branch] = release; return SimpleNamespace(returncode=1, stdout="", stderr="lost")
    got = mod.push_release_branch(api, release, runner=runner, branch=branch)
    assert got == branch and len(calls) == 1


def test_wait_exact_ci_rejects_failed_terminal_run():
    api = GhApi(); release = "c" * 40; branch = "shadow-release-c"
    api.runs = [{"id": 9, "run_number": 4, "head_sha": release, "head_branch": branch, "path": ".github/workflows/ci.yml", "status": "completed", "conclusion": "failure"}]
    with pytest.raises(mod.ShadowProvisionError, match="GITHUB_RELEASE_EXACT_HEAD_CI_FAILED"):
        mod.wait_exact_ci(api, release, branch, timeout_seconds=1, sleep=lambda _: None)


def test_destructive_migration_gate_stops_before_dispatch(tmp_path, monkeypatch):
    api = CfApi(); config = tmp_path / "wrangler.jsonc"; config.write_text("{}")
    monkeypatch.setattr(mod.d1r, "require_expand_only", lambda pending: (_ for _ in ()).throw(mod.d1r.D1RecoveryError("D1_DESTRUCTIVE_MIGRATION_BLOCKED:test.sql")))
    called = []
    with pytest.raises(mod.ShadowProvisionError, match="D1_DESTRUCTIVE_MIGRATION_BLOCKED"):
        mod.ensure_migrations(api, DB, config, runner=lambda *args, **kwargs: called.append(args))
    assert called == []
