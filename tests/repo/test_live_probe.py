from __future__ import annotations

import importlib.util
import pathlib
import sys
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("live_probe", ROOT / "scripts/live_probe.py")
mod = importlib.util.module_from_spec(spec)
assert spec.loader
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)

HEAD = "a" * 40
BASE = "https://fare-radar.example.workers.dev"


def test_runtime_identity_is_exact(monkeypatch):
    monkeypatch.setattr(mod, "_request", lambda *a, **k: mod.HttpResult(200,{"ok":True,"spec":"1.3","commit_sha":HEAD,"deployment_mode":"SHADOW_ACCEPTANCE"}))
    assert mod.verify_runtime(BASE,HEAD,"SHADOW_ACCEPTANCE")["commit_sha"] == HEAD
    with pytest.raises(mod.LiveProbeError, match="LIVE_PROBE_RUNTIME_IDENTITY_MISMATCH"):
        mod.verify_runtime(BASE,"b"*40,"SHADOW_ACCEPTANCE")


def test_worker_token_probe_accepts_only_authenticated_missing_lease(monkeypatch):
    monkeypatch.setattr(mod, "_request", lambda *a, **k: mod.HttpResult(403,{"error":"LIVE_SOURCE_LEASE_REQUIRED"}))
    mod.probe_worker_token(BASE,"secret")
    monkeypatch.setattr(mod, "_request", lambda *a, **k: mod.HttpResult(401,{"error":"UNAUTHORIZED"}))
    with pytest.raises(mod.LiveProbeError, match="WORKER_TOKEN_PROBE_UNAUTHORIZED"):
        mod.probe_worker_token(BASE,"wrong")


def test_reviewer_probes_require_authenticated_empty_readback(monkeypatch):
    def ok(url, **kwargs):
        if url.endswith('/shadow/reviews/readback'): return mod.HttpResult(200,{"review":None})
        if url.endswith('/audit/evidence/readback'): return mod.HttpResult(200,{"evidence":None})
        raise AssertionError(url)
    monkeypatch.setattr(mod, "_request", ok)
    mod.probe_reviewer(BASE,key_id="shadow",secret="s"*16,role="SHADOW_REVIEWER")
    mod.probe_reviewer(BASE,key_id="access",secret="a"*16,role="ACCESS_REVIEWER")
    monkeypatch.setattr(mod, "_request", lambda *a, **k: mod.HttpResult(401,{"error":"UNAUTHORIZED"}))
    with pytest.raises(mod.LiveProbeError, match="SHADOW_REVIEWER_PROBE_UNAUTHORIZED"):
        mod.probe_reviewer(BASE,key_id="shadow",secret="x"*16,role="SHADOW_REVIEWER")


def test_run_probes_orders_identity_before_credentials(monkeypatch):
    calls=[]
    monkeypatch.setattr(mod,"verify_runtime",lambda base,head,mode:(calls.append("health") or {"spec":"1.3"}))
    monkeypatch.setattr(mod,"probe_worker_token",lambda base,token:calls.append("worker"))
    monkeypatch.setattr(mod,"probe_reviewer",lambda base,**kwargs:calls.append(kwargs["role"]))
    result=mod.run_probes(base_url=BASE,expected_head=HEAD,expected_mode="SHADOW_ACCEPTANCE",worker_token="w",shadow_key_id="s",shadow_secret="s"*16,access_key_id="a",access_secret="a"*16)
    assert result["ok"] is True
    assert calls == ["health","worker","SHADOW_REVIEWER","ACCESS_REVIEWER"]
