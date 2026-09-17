from __future__ import annotations

import importlib.util
import pathlib
import subprocess
import sys
from types import SimpleNamespace
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location("deploy_shadow", ROOT / "scripts/deploy_shadow.py")
mod = importlib.util.module_from_spec(spec)
assert spec.loader
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)

HEAD = "a" * 40
DB = "11111111-2222-3333-4444-555555555555"


def env(monkeypatch):
    values = {
        "FARE_SHADOW_EXPECTED_HEAD": HEAD,
        "CLOUDFLARE_API_TOKEN": "token",
        "CLOUDFLARE_ACCOUNT_ID": "acct",
        "FARE_D1_DATABASE_ID": DB,
        "FARE_WORKER_TOKEN": "worker-secret",
        "FARE_SHADOW_REVIEWER_KEY_ID": "shadow-key",
        "FARE_SHADOW_REVIEWER_SECRET": "s" * 24,
        "FARE_ACCESS_REVIEWER_KEY_ID": "access-key",
        "FARE_ACCESS_REVIEWER_SECRET": "a" * 24,
    }
    for k,v in values.items(): monkeypatch.setenv(k,v)


def common(monkeypatch):
    env(monkeypatch)
    monkeypatch.setattr(mod, "require_clean_exact_head", lambda expected: HEAD)
    monkeypatch.setattr(mod.preflight, "code_ready", lambda head: True)
    monkeypatch.setattr(mod, "d1_id", lambda: DB)


def state():
    return {"worker_origin":"https://fare-radar.acct.workers.dev","version_id":"v-new","commit_sha":HEAD,"deployment_mode":"SHADOW_ACCEPTANCE"}


def test_build_precedes_one_shadow_only_deploy(monkeypatch):
    common(monkeypatch); calls=[]
    def runner(args, **kwargs):
        calls.append(args)
        return SimpleNamespace(returncode=0,stdout="",stderr="")
    monkeypatch.setattr(mod,"worker_snapshot",lambda api,name: mod.WorkerSnapshot(True,"old","SHADOW_ACCEPTANCE","dep-old","v-old"))
    probes=[]
    result=mod.deploy_shadow(runner=runner,api_factory=lambda a,t:object(),readback=lambda *a,**k:state(),probes=lambda **k:(probes.append(k) or {"ok":True}))
    assert result["ok"] is True
    assert calls[0] == ["npm","run","build"]
    assert calls[1].count("deploy") == 1
    joined=" ".join(calls[1])
    assert "wrangler@4.131.2" in joined and "--keep-vars" in calls[1] and "--strict" in calls[1]
    assert f"FARE_COMMIT_SHA:{HEAD}" in calls[1]
    assert "FARE_DEPLOYMENT_MODE:SHADOW_ACCEPTANCE" in calls[1]
    assert "PRODUCTION" not in joined
    assert len(probes) == 1


def test_unknown_deploy_is_never_resent_when_readback_confirms(monkeypatch):
    common(monkeypatch); calls=[]
    def runner(args, **kwargs):
        calls.append(args)
        return SimpleNamespace(returncode=0 if args[:3]==["npm","run","build"] else 1,stdout="",stderr="lost response")
    monkeypatch.setattr(mod,"worker_snapshot",lambda api,name: mod.WorkerSnapshot(True,"old","SHADOW_ACCEPTANCE","dep-old","v-old"))
    result=mod.deploy_shadow(runner=runner,api_factory=lambda a,t:object(),readback=lambda *a,**k:state(),probes=lambda **k:{"ok":True})
    assert result["deploy_command_uncertain_but_readback_confirmed"] is True
    assert len([x for x in calls if "deploy" in x]) == 1


def test_unknown_deploy_not_applied_vs_ambiguous(monkeypatch):
    common(monkeypatch)
    runner=lambda args,**kwargs: SimpleNamespace(returncode=0 if args[:3]==["npm","run","build"] else 1,stdout="",stderr="")
    readback=lambda *a,**k: (_ for _ in ()).throw(mod.cf.CloudflareProviderError("mismatch"))
    before=mod.WorkerSnapshot(True,"old","SHADOW_ACCEPTANCE","dep-old","v-old")
    seq=iter([before,before])
    monkeypatch.setattr(mod,"worker_snapshot",lambda api,name: next(seq))
    with pytest.raises(mod.ShadowDeployError,match="SHADOW_DEPLOY_NOT_APPLIED"):
        mod.deploy_shadow(runner=runner,api_factory=lambda a,t:object(),readback=readback,probes=lambda **k:{})

    changed=mod.WorkerSnapshot(True,HEAD,"SHADOW_ACCEPTANCE","dep-new","v-partial")
    seq=iter([before,changed]); monkeypatch.setattr(mod,"worker_snapshot",lambda api,name: next(seq))
    with pytest.raises(mod.ShadowDeployError,match="SHADOW_DEPLOY_PARTIAL_OR_AMBIGUOUS"):
        mod.deploy_shadow(runner=runner,api_factory=lambda a,t:object(),readback=readback,probes=lambda **k:{})


def test_build_failure_stops_before_provider_read_or_deploy(monkeypatch):
    common(monkeypatch); calls=[]
    def runner(args,**kwargs): calls.append(args); return SimpleNamespace(returncode=1,stdout="",stderr="build fail")
    with pytest.raises(mod.ShadowDeployError,match="SHADOW_BUILD_FAILED"):
        mod.deploy_shadow(runner=runner,api_factory=lambda a,t:(_ for _ in ()).throw(AssertionError("provider should not be touched")))
    assert calls == [["npm","run","build"]]
