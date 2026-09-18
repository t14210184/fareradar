from __future__ import annotations

import importlib.util
import pathlib
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
OLD_HEAD = "b" * 40
DB = "11111111-2222-3333-4444-555555555555"
OLD = "11111111-1111-4111-8111-111111111111"
NEW = "22222222-2222-4222-8222-222222222222"
PREVIEW = f"https://shadow-{HEAD[:12]}-fare-radar.acct.workers.dev"
ORIGIN = "https://fare-radar.acct.workers.dev"


def common(monkeypatch):
    for key, value in {
        "FARE_SHADOW_EXPECTED_HEAD": HEAD,
        "CLOUDFLARE_API_TOKEN": "token",
        "CLOUDFLARE_ACCOUNT_ID": "acct",
        "FARE_D1_DATABASE_ID": DB,
        "FARE_WORKER_TOKEN": "worker-secret",
        "FARE_SHADOW_REVIEWER_KEY_ID": "shadow-key",
        "FARE_SHADOW_REVIEWER_SECRET": "s" * 24,
        "FARE_ACCESS_REVIEWER_KEY_ID": "access-key",
        "FARE_ACCESS_REVIEWER_SECRET": "a" * 24,
    }.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(mod, "require_clean_exact_head", lambda expected: HEAD)
    monkeypatch.setattr(mod.preflight, "code_ready", lambda head: True)
    monkeypatch.setattr(mod, "d1_id", lambda: DB)
    monkeypatch.setattr(mod.cf, "write_bootstrap_evidence", lambda state: None)


def state(head=HEAD, version=NEW):
    return {
        "worker_origin": ORIGIN,
        "deployment_id": "dep-new",
        "version_id": version,
        "commit_sha": head,
        "deployment_mode": "SHADOW_ACCEPTANCE",
    }


def runner(args, **kwargs):
    if args == ["npm", "run", "build"]:
        return SimpleNamespace(returncode=0, stdout="", stderr="")
    return SimpleNamespace(returncode=0, stdout="", stderr="")


def test_first_worker_bootstrap_keeps_one_coupled_deploy(monkeypatch):
    common(monkeypatch)
    monkeypatch.setattr(mod, "worker_snapshot", lambda api, name: mod.WorkerSnapshot(False, None, None, None, None))
    calls = []

    def capture(args, **kwargs):
        calls.append(args)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    result = mod.deploy_shadow(
        runner=capture,
        api_factory=lambda account, token: object(),
        readback=lambda *args, **kwargs: state(),
        probes=lambda **kwargs: {"ok": True},
    )
    deploys = [item for item in calls if "deploy" in item]
    assert result["deploy_strategy"] == "INITIAL_BOOTSTRAP"
    assert len(deploys) == 1
    assert "versions" not in deploys[0]


def test_existing_shadow_uses_preview_then_exact_version_activation(monkeypatch):
    common(monkeypatch)
    monkeypatch.setattr(
        mod,
        "worker_snapshot",
        lambda api, name: mod.WorkerSnapshot(True, OLD_HEAD, "SHADOW_ACCEPTANCE", "dep-old", OLD),
    )
    monkeypatch.setattr(
        mod.release,
        "upload_version_candidate",
        lambda **kwargs: mod.release.UploadedVersion(NEW, PREVIEW, True),
    )
    monkeypatch.setattr(
        mod.release,
        "deploy_version_100",
        lambda **kwargs: mod.release.DeploymentChange("dep-new", NEW, True, False),
    )
    probes = []
    result = mod.deploy_shadow(
        runner=runner,
        api_factory=lambda account, token: object(),
        readback=lambda *args, **kwargs: state(),
        probes=lambda **kwargs: (probes.append(kwargs) or {"ok": True}),
    )
    assert result["deploy_strategy"] == "VERSIONED_SHADOW_UPDATE"
    assert result["previous_shadow_version_id"] == OLD
    assert result["candidate_version_id"] == NEW
    assert [item["base_url"] for item in probes] == [PREVIEW, ORIGIN]


def test_existing_production_or_partial_worker_is_never_overwritten(monkeypatch):
    common(monkeypatch)
    for snapshot in (
        mod.WorkerSnapshot(True, OLD_HEAD, "PRODUCTION", "dep-old", OLD),
        mod.WorkerSnapshot(True, None, None, None, None),
    ):
        monkeypatch.setattr(mod, "worker_snapshot", lambda api, name, snapshot=snapshot: snapshot)
        with pytest.raises(mod.ShadowDeployError, match="SHADOW_EXISTING_PRESTATE_NOT_SAFE"):
            mod.deploy_shadow(runner=runner, api_factory=lambda account, token: object())


def test_preview_failure_never_activates(monkeypatch):
    common(monkeypatch)
    monkeypatch.setattr(
        mod,
        "worker_snapshot",
        lambda api, name: mod.WorkerSnapshot(True, OLD_HEAD, "SHADOW_ACCEPTANCE", "dep-old", OLD),
    )
    monkeypatch.setattr(
        mod.release,
        "upload_version_candidate",
        lambda **kwargs: mod.release.UploadedVersion(NEW, PREVIEW, False),
    )
    activation = []
    monkeypatch.setattr(mod.release, "deploy_version_100", lambda **kwargs: activation.append(kwargs))
    with pytest.raises(mod.ShadowDeployError, match="SHADOW_PREVIEW_VALIDATION_FAILED"):
        mod.deploy_shadow(
            runner=runner,
            api_factory=lambda account, token: object(),
            probes=lambda **kwargs: (_ for _ in ()).throw(mod.live_probe.LiveProbeError("bad")),
        )
    assert activation == []


def test_postdeploy_failure_rolls_back_previous_shadow(monkeypatch):
    common(monkeypatch)
    before = mod.WorkerSnapshot(True, OLD_HEAD, "SHADOW_ACCEPTANCE", "dep-old", OLD)
    monkeypatch.setattr(mod, "worker_snapshot", lambda api, name: before)
    monkeypatch.setattr(
        mod.release,
        "upload_version_candidate",
        lambda **kwargs: mod.release.UploadedVersion(NEW, PREVIEW, False),
    )
    monkeypatch.setattr(
        mod.release,
        "deploy_version_100",
        lambda **kwargs: mod.release.DeploymentChange("dep-new", NEW, False, False),
    )
    rolled = []
    monkeypatch.setattr(
        mod.release,
        "rollback_to_version",
        lambda **kwargs: (
            rolled.append(kwargs)
            or mod.release.DeploymentChange("dep-rollback", OLD, True, False)
        ),
    )
    monkeypatch.setattr(
        mod.cf,
        "collect_bootstrap_readback",
        lambda *args, **kwargs: state(OLD_HEAD, OLD),
    )
    probes = []

    def probe(**kwargs):
        probes.append(kwargs)
        return {"ok": True}

    with pytest.raises(mod.ShadowDeployError, match="SHADOW_POSTDEPLOY_VALIDATION_FAILED_ROLLED_BACK"):
        mod.deploy_shadow(
            runner=runner,
            api_factory=lambda account, token: object(),
            readback=lambda *args, **kwargs: (_ for _ in ()).throw(mod.cf.CloudflareProviderError("bad")),
            probes=probe,
        )
    assert rolled[0]["version_id"] == OLD
    assert probes[0]["base_url"] == PREVIEW
    assert probes[-1]["expected_head"] == OLD_HEAD


def test_worker_snapshot_only_treats_both_missing_as_absent():
    class Api:
        def __init__(self, settings, deployments):
            self.settings = settings
            self.deployments = deployments

        def get(self, path):
            if path.endswith("/settings"):
                return mod.cf.Response(200, {"success": True, "result": self.settings})
            return mod.cf.Response(200, {"success": True, "result": self.deployments})

    absent = mod.worker_snapshot(Api(None, None), "fare-radar")
    partial = mod.worker_snapshot(Api({"bindings": []}, None), "fare-radar")
    assert absent.exists is False
    assert partial.exists is True
    assert partial.version_id is None


def test_build_failure_stops_before_provider_access(monkeypatch):
    common(monkeypatch)
    calls = []

    def failed(args, **kwargs):
        calls.append(args)
        return SimpleNamespace(returncode=1, stdout="", stderr="build fail")

    with pytest.raises(mod.ShadowDeployError, match="SHADOW_BUILD_FAILED"):
        mod.deploy_shadow(
            runner=failed,
            api_factory=lambda account, token: (_ for _ in ()).throw(AssertionError("provider touched")),
        )
    assert calls == [["npm", "run", "build"]]
