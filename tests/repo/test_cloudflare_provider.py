from __future__ import annotations

import importlib.util
import pathlib
import sys
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("cloudflare_provider", ROOT / "scripts/cloudflare_provider.py")
mod = importlib.util.module_from_spec(spec)
assert spec.loader
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)

ACCOUNT = "a" * 32
DB = "11111111-2222-3333-4444-555555555555"
HEAD = "b" * 40
WORKER = "fare-radar"
MODE = "SHADOW_ACCEPTANCE"

def envelope(result):
    return mod.Response(200, {"success": True, "errors": [], "messages": [], "result": result})

class Api:
    def __init__(self):
        self.migrations = mod._migration_names()
        self.sources = sorted(mod._seed_ids(ROOT / "config" / "sources.seed.json", "source_id"))
        self.providers = sorted(mod._seed_ids(ROOT / "config" / "providers.seed.json", "provider_id"))
        self.bindings = [
            {"name":"DB","type":"d1","id":DB},
            {"name":"FARE_COMMIT_SHA","type":"plain_text","text":HEAD},
            {"name":"FARE_DEPLOYMENT_MODE","type":"plain_text","text":MODE},
        ]
        self.versions = [{"version_id":"v1","percentage":100}]
        self.crons = [{"cron":"* * * * *"}]
        self.account_subdomain = "acct"
        self.script_subdomain_enabled = True
        self.secrets = [{"name":"WORKER_TOKEN"},{"name":"INGEST_HMAC_SECRETS"}]
        self.missing_source_review = False
        self.missing_provider_review = False
    def get(self, path):
        if path == f"/d1/database/{DB}": return envelope({"uuid":DB,"name":"fare-radar-production"})
        if path == f"/workers/scripts/{WORKER}/settings": return envelope({"bindings":self.bindings})
        if path == f"/workers/scripts/{WORKER}/deployments": return envelope({"deployments":[{"id":"dep1","versions":self.versions}]})
        if path == f"/workers/scripts/{WORKER}/schedules": return envelope({"schedules":self.crons})
        if path == "/workers/subdomain": return envelope({"subdomain":self.account_subdomain})
        if path == f"/workers/scripts/{WORKER}/subdomain": return envelope({"enabled":self.script_subdomain_enabled,"previews_enabled":False})
        if path == f"/workers/scripts/{WORKER}/secrets": return envelope(self.secrets)
        raise AssertionError(path)
    def post(self, path, payload):
        assert path == f"/d1/database/{DB}/query"
        sql = payload["sql"]
        if "FROM d1_migrations" in sql:
            rows = [{"name":x} for x in self.migrations]
        elif "SELECT source_id FROM source_registry" in sql:
            rows = [{"source_id":x} for x in self.sources]
        elif "SELECT provider_id FROM provider_access_registry" in sql:
            rows = [{"provider_id":x} for x in self.providers]
        elif "SELECT s.source_id FROM source_registry s" in sql:
            rows = [{"source_id":"bad-source"}] if self.missing_source_review else []
        elif "SELECT p.provider_id FROM provider_access_registry p" in sql:
            rows = [{"provider_id":"bad-provider"}] if self.missing_provider_review else []
        else:
            raise AssertionError(sql)
        return envelope([{"success":True,"results":rows}])

def collect(api):
    return mod.collect_readback(api, account_id=ACCOUNT, database_id=DB, worker_name=WORKER, expected_head=HEAD, expected_mode=MODE)

def test_collects_one_same_source_snapshot():
    state = collect(Api())
    assert state["provider"] == "cloudflare"
    assert state["database_id"] == DB
    assert state["commit_sha"] == HEAD
    assert state["version_id"] == "v1"
    assert state["worker_origin"] == "https://fare-radar.acct.workers.dev"
    assert state["cron_schedules"] == ["* * * * *"]
    assert state["migrations_verified"] is True
    assert state["baseline_seeds_verified"] is True
    assert state["dispatchable_reviews_verified"] is True
    assert set(state["secret_names"]) >= mod.REQUIRED_SECRETS
    assert state["readback_session_id"]

def test_rejects_wrong_binding_and_split_deployment():
    api = Api(); api.bindings[0]["id"] = "wrong"
    with pytest.raises(mod.CloudflareProviderError, match="WORKER_D1_BINDING_MISMATCH"): collect(api)
    api = Api(); api.versions = [{"version_id":"v1","percentage":50},{"version_id":"v2","percentage":50}]
    with pytest.raises(mod.CloudflareProviderError, match="WORKER_ACTIVE_VERSION_NOT_SINGLE_100_PERCENT"): collect(api)

def test_rejects_cron_or_origin_drift():
    api = Api(); api.crons = [{"cron":"*/5 * * * *"}]
    with pytest.raises(mod.CloudflareProviderError, match="WORKER_CRON_SET_MISMATCH"): collect(api)
    api = Api(); api.script_subdomain_enabled = False
    with pytest.raises(mod.CloudflareProviderError, match="WORKER_ORIGIN_UNAVAILABLE"): collect(api)
    api = Api(); api.account_subdomain = ""
    with pytest.raises(mod.CloudflareProviderError, match="WORKER_ORIGIN_UNAVAILABLE"): collect(api)

def test_rejects_migration_seed_and_review_drift():
    api = Api(); api.migrations = api.migrations[:-1]
    with pytest.raises(mod.CloudflareProviderError, match="D1_MIGRATION_SET_MISMATCH"): collect(api)
    api = Api(); api.sources = api.sources[:-1]
    with pytest.raises(mod.CloudflareProviderError, match="SOURCE_BASELINE_SEEDS_MISSING"): collect(api)
    api = Api(); api.missing_source_review = True
    with pytest.raises(mod.CloudflareProviderError, match="DISPATCHABLE_SOURCE_REVIEW_MISSING"): collect(api)
    api = Api(); api.missing_provider_review = True
    with pytest.raises(mod.CloudflareProviderError, match="DISPATCHABLE_PROVIDER_REVIEW_MISSING"): collect(api)

def test_rejects_missing_required_or_legacy_secret_and_identity_drift():
    api = Api(); api.secrets = [{"name":"WORKER_TOKEN"}]
    with pytest.raises(mod.CloudflareProviderError, match="REQUIRED_WORKER_SECRETS_MISSING"): collect(api)
    api = Api(); api.secrets.append({"name":"LEGACY_INGEST_TOKEN"})
    with pytest.raises(mod.CloudflareProviderError, match="LEGACY_INGEST_SECRET_PRESENT"): collect(api)
    api = Api(); api.bindings[1]["text"] = "c" * 40
    with pytest.raises(mod.CloudflareProviderError, match="WORKER_COMMIT_BINDING_MISMATCH"): collect(api)
    api = Api(); api.bindings[2]["text"] = "PRODUCTION"
    with pytest.raises(mod.CloudflareProviderError, match="WORKER_DEPLOYMENT_MODE_MISMATCH"): collect(api)
