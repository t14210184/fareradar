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
OLD = "11111111-1111-4111-8111-111111111111"
NEW = "22222222-2222-4222-8222-222222222222"
PREVIEW = f"https://prod-{HEAD[:12]}-fare-radar.acct.workers.dev"
ORIGIN = "https://fare-radar.acct.workers.dev"


def setup(monkeypatch):
    for key, value in {
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
    monkeypatch.setattr(mod, "require_human_approved_exact_head", lambda: HEAD)
    monkeypatch.setattr(mod.preflight, "evaluate", lambda: {"blockers": ["PRODUCTION_ACTIVATION_REQUIRED"]})
    monkeypatch.setattr(mod.shadow, "d1_id", lambda: DB)
    monkeypatch.setattr(mod.cf, "write_evidence", lambda state: None)
    monkeypatch.setattr(
        mod.shadow,
        "worker_snapshot",
        lambda api, name: mod.shadow.WorkerSnapshot(True, HEAD, "SHADOW_ACCEPTANCE", "dep-shadow", OLD),
    )


def prod_state():
    return {
        "worker_origin": ORIGIN,
        "version_id": NEW,
        "deployment_id": "dep-prod",
        "commit_sha": HEAD,
        "deployment_mode": "PRODUCTION",
        "dispatchable_reviews_verified": True,
    }


def shadow_state():
    return {
        "worker_origin": ORIGIN,
        "version_id": OLD,
        "deployment_id": "dep-rollback",
        "commit_sha": HEAD,
        "deployment_mode": "SHADOW_ACCEPTANCE",
    }


def runner(args, **kwargs):
    assert args == ["npm", "run", "build"]
    return SimpleNamespace(returncode=0, stdout="", stderr="")


def test_preview_passes_before_exact_activation(monkeypatch):
    setup(monkeypatch)
    monkeypatch.setattr(
        mod.release,
        "upload_version_candidate",
        lambda **kwargs: mod.release.UploadedVersion(NEW, PREVIEW, False),
    )
    monkeypatch.setattr(
        mod.release,
        "deploy_version_100",
        lambda **kwargs: mod.release.DeploymentChange("dep-prod", NEW, False, False),
    )
    probes = []
    result = mod.deploy_production(
        runner=runner,
        api_factory=lambda account, token: object(),
        readback=lambda *args, **kwargs: prod_state(),
        probes=lambda **kwargs: (probes.append(kwargs) or {"ok": True}),
    )
    assert [item["base_url"] for item in probes] == [PREVIEW, ORIGIN]
    assert result["candidate_version_id"] == NEW
    assert result["previous_shadow_version_id"] == OLD
    assert result["rollback_boundary"] == "WORKER_VERSION_ONLY_D1_NOT_ROLLED_BACK"


def test_preview_failure_never_activates(monkeypatch):
    setup(monkeypatch)
    monkeypatch.setattr(
        mod.release,
        "upload_version_candidate",
        lambda **kwargs: mod.release.UploadedVersion(NEW, PREVIEW, False),
    )
    activated = []
    monkeypatch.setattr(mod.release, "deploy_version_100", lambda **kwargs: activated.append(kwargs))
    with pytest.raises(mod.ProductionDeployError, match="PRODUCTION_PREVIEW_VALIDATION_FAILED"):
        mod.deploy_production(
            runner=runner,
            api_factory=lambda account, token: object(),
            probes=lambda **kwargs: (_ for _ in ()).throw(mod.live_probe.LiveProbeError("bad")),
        )
    assert activated == []


def test_postdeploy_failure_restores_shadow_version(monkeypatch):
    setup(monkeypatch)
    monkeypatch.setattr(
        mod.release,
        "upload_version_candidate",
        lambda **kwargs: mod.release.UploadedVersion(NEW, PREVIEW, True),
    )
    monkeypatch.setattr(
        mod.release,
        "deploy_version_100",
        lambda **kwargs: mod.release.DeploymentChange("dep-prod", NEW, True, False),
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
    monkeypatch.setattr(mod.cf, "collect_bootstrap_readback", lambda *args, **kwargs: shadow_state())
    modes = []

    def probes(**kwargs):
        modes.append(kwargs["expected_mode"])
        return {"ok": True}

    with pytest.raises(mod.ProductionDeployError, match="PRODUCTION_POSTDEPLOY_VALIDATION_FAILED_ROLLED_BACK"):
        mod.deploy_production(
            runner=runner,
            api_factory=lambda account, token: object(),
            readback=lambda *args, **kwargs: (_ for _ in ()).throw(mod.cf.CloudflareProviderError("bad")),
            probes=probes,
        )
    assert rolled[0]["version_id"] == OLD
    assert modes == ["PRODUCTION", "SHADOW_ACCEPTANCE"]


def test_activation_error_also_reconciles_to_shadow(monkeypatch):
    setup(monkeypatch)
    monkeypatch.setattr(
        mod.release,
        "upload_version_candidate",
        lambda **kwargs: mod.release.UploadedVersion(NEW, PREVIEW, False),
    )
    monkeypatch.setattr(
        mod.release,
        "deploy_version_100",
        lambda **kwargs: (_ for _ in ()).throw(mod.release.CloudflareReleaseError("ambiguous")),
    )
    monkeypatch.setattr(
        mod.release,
        "rollback_to_version",
        lambda **kwargs: mod.release.DeploymentChange("dep-rollback", OLD, False, False),
    )
    monkeypatch.setattr(mod.cf, "collect_bootstrap_readback", lambda *args, **kwargs: shadow_state())
    with pytest.raises(mod.ProductionDeployError, match="PRODUCTION_VERSION_ACTIVATION_FAILED_ROLLED_BACK"):
        mod.deploy_production(
            runner=runner,
            api_factory=lambda account, token: object(),
            probes=lambda **kwargs: {"ok": True},
        )


def test_prerequisites_and_exact_shadow_prestate_remain_mandatory(monkeypatch):
    setup(monkeypatch)
    monkeypatch.setattr(mod.preflight, "evaluate", lambda: {"blockers": ["SHADOW_ACCEPTANCE_MISSING"]})
    with pytest.raises(mod.ProductionDeployError, match="PRODUCTION_PREREQUISITES_NOT_SATISFIED"):
        mod.deploy_production(runner=runner)

    setup(monkeypatch)
    monkeypatch.setattr(
        mod.shadow,
        "worker_snapshot",
        lambda api, name: mod.shadow.WorkerSnapshot(True, HEAD, "PRODUCTION", "dep", NEW),
    )
    with pytest.raises(mod.ProductionDeployError, match="PRODUCTION_PRESTATE_NOT_EXACT_SHADOW"):
        mod.deploy_production(runner=runner, api_factory=lambda account, token: object())
