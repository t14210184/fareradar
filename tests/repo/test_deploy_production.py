from __future__ import annotations

import importlib.util
import pathlib
import sys
from types import SimpleNamespace
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location("deploy_production", ROOT / "scripts/deploy_production.py")
mod = importlib.util.module_from_spec(spec)
assert spec.loader
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)

HEAD = "a" * 40
DB = "11111111-2222-3333-4444-555555555555"


def env(monkeypatch):
    values={
        "CLOUDFLARE_API_TOKEN":"token","CLOUDFLARE_ACCOUNT_ID":"acct","FARE_D1_DATABASE_ID":DB,
        "FARE_WORKER_TOKEN":"worker-secret","FARE_SHADOW_REVIEWER_KEY_ID":"shadow-key","FARE_SHADOW_REVIEWER_SECRET":"s"*24,
        "FARE_ACCESS_REVIEWER_KEY_ID":"access-key","FARE_ACCESS_REVIEWER_SECRET":"a"*24,
    }
    for k,v in values.items(): monkeypatch.setenv(k,v)


def common(monkeypatch):
    env(monkeypatch)
    monkeypatch.setattr(mod,"require_human_approved_exact_head",lambda:HEAD)
    monkeypatch.setattr(mod.preflight,"evaluate",lambda:{"blockers":["PRODUCTION_ACTIVATION_REQUIRED"]})
    monkeypatch.setattr(mod.shadow,"d1_id",lambda:DB)
    monkeypatch.setattr(mod.cf,"write_evidence",lambda state:None)


def state():
    return {"readback_session_id":"session-1","observed_at":"2026-09-17T15:00:00Z","provider":"cloudflare","account_id":"acct","database_id":DB,"worker_name":"fare-radar","worker_origin":"https://fare-radar.acct.workers.dev","cron_schedules":["* * * * *"],"deployment_id":"dep-prod","version_id":"v-prod","commit_sha":HEAD,"deployment_mode":"PRODUCTION","binding_verified":True,"migrations_verified":True,"baseline_seeds_verified":True,"dispatchable_reviews_verified":True,"secret_names":["WORKER_TOKEN","INGEST_HMAC_SECRETS"],"legacy_ingest_auth_enabled":False}


def test_human_approval_is_mandatory_and_exact(monkeypatch):
    monkeypatch.delenv("FARE_PRODUCTION_HUMAN_APPROVED_HEAD",raising=False)
    monkeypatch.setattr(mod.shadow,"git",lambda *args:"")
    monkeypatch.setattr(mod.shadow,"local_head",lambda:HEAD)
    with pytest.raises(mod.ProductionDeployError,match="PRODUCTION_HUMAN_APPROVAL_REQUIRED"):
        mod.require_human_approved_exact_head()
    monkeypatch.setenv("FARE_PRODUCTION_HUMAN_APPROVED_HEAD","b"*40)
    with pytest.raises(mod.ProductionDeployError,match="PRODUCTION_HUMAN_APPROVAL_HEAD_MISMATCH"):
        mod.require_human_approved_exact_head()


def test_only_activation_blocker_allows_production(monkeypatch):
    common(monkeypatch)
    monkeypatch.setattr(mod.preflight,"evaluate",lambda:{"blockers":["SHADOW_ACCEPTANCE_MISSING","PRODUCTION_ACTIVATION_REQUIRED"]})
    calls=[]
    with pytest.raises(mod.ProductionDeployError,match="PRODUCTION_PREREQUISITES_NOT_SATISFIED"):
        mod.deploy_production(runner=lambda args,**kwargs:(calls.append(args) or SimpleNamespace(returncode=0)))
    assert calls == []


def test_build_then_exact_shadow_prestate_then_one_production_deploy(monkeypatch):
    common(monkeypatch); calls=[]
    def runner(args,**kwargs): calls.append(args); return SimpleNamespace(returncode=0,stdout="",stderr="")
    monkeypatch.setattr(mod.shadow,"worker_snapshot",lambda api,name:mod.shadow.WorkerSnapshot(True,HEAD,"SHADOW_ACCEPTANCE","dep-shadow","v-shadow"))
    probes=[]
    result=mod.deploy_production(runner=runner,api_factory=lambda a,t:object(),readback=lambda *a,**k:state(),probes=lambda **k:(probes.append(k) or {"ok":True}))
    assert result["ok"] and result["deployment_mode"] == "PRODUCTION"
    assert calls[0] == ["npm","run","build"]
    deploys=[x for x in calls if "deploy" in x]
    assert len(deploys)==1
    joined=" ".join(deploys[0])
    assert "FARE_DEPLOYMENT_MODE:PRODUCTION" in deploys[0]
    assert "SHADOW_ACCEPTANCE" not in joined
    assert "--strict" in deploys[0] and "--keep-vars" in deploys[0]
    assert len(probes)==1 and probes[0]["expected_mode"]=="PRODUCTION"


def test_production_prestate_must_still_be_exact_shadow(monkeypatch):
    common(monkeypatch)
    runner=lambda args,**kwargs:SimpleNamespace(returncode=0,stdout="",stderr="")
    monkeypatch.setattr(mod.shadow,"worker_snapshot",lambda api,name:mod.shadow.WorkerSnapshot(True,HEAD,"PRODUCTION","dep","v"))
    with pytest.raises(mod.ProductionDeployError,match="PRODUCTION_PRESTATE_NOT_EXACT_SHADOW"):
        mod.deploy_production(runner=runner,api_factory=lambda a,t:object())


def test_lost_deploy_response_is_readback_first_and_never_resent(monkeypatch):
    common(monkeypatch); calls=[]
    def runner(args,**kwargs):
        calls.append(args)
        return SimpleNamespace(returncode=0 if args[:3]==["npm","run","build"] else 1,stdout="",stderr="lost")
    monkeypatch.setattr(mod.shadow,"worker_snapshot",lambda api,name:mod.shadow.WorkerSnapshot(True,HEAD,"SHADOW_ACCEPTANCE","dep-shadow","v-shadow"))
    result=mod.deploy_production(runner=runner,api_factory=lambda a,t:object(),readback=lambda *a,**k:state(),probes=lambda **k:{"ok":True})
    assert result["deploy_command_uncertain_but_readback_confirmed"] is True
    assert len([x for x in calls if "deploy" in x])==1
