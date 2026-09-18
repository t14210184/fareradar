from __future__ import annotations

import importlib.util
import pathlib
import sys
from types import SimpleNamespace

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location("cloudflare_release", ROOT / "scripts/cloudflare_release.py")
mod = importlib.util.module_from_spec(spec)
assert spec.loader
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)

WORKER = "fare-radar"
HEAD = "a" * 40
OLD = "11111111-1111-4111-8111-111111111111"
NEW = "22222222-2222-4222-8222-222222222222"


def envelope(result):
    return mod.cf.Response(200, {"success": True, "errors": [], "messages": [], "result": result})


class Api:
    def __init__(self):
        self.versions = {OLD}
        self.active = OLD
        self.deployment_seq = 1
        self.previews_enabled = True

    def get(self, path):
        if path == f"/workers/scripts/{WORKER}/versions":
            return envelope({"items": [{"id": value} for value in sorted(self.versions)]})
        if path == f"/workers/scripts/{WORKER}/deployments":
            return envelope({
                "deployments": [{
                    "id": f"dep-{self.deployment_seq}",
                    "versions": [{"version_id": self.active, "percentage": 100}],
                }]
            })
        if path == "/workers/subdomain":
            return envelope({"subdomain": "acct"})
        if path == f"/workers/scripts/{WORKER}/subdomain":
            return envelope({"enabled": True, "previews_enabled": self.previews_enabled})
        raise AssertionError(path)

    def activate(self, version_id):
        self.active = version_id
        self.deployment_seq += 1


def test_upload_candidate_is_zero_traffic_and_readback_identified():
    api = Api()
    calls = []

    def runner(args, **kwargs):
        calls.append(args)
        api.versions.add(NEW)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    result = mod.upload_version_candidate(
        runner=runner,
        api=api,
        worker_name=WORKER,
        head=HEAD,
        mode="PRODUCTION",
    )
    assert result.version_id == NEW
    assert result.preview_url == f"https://candidate-{HEAD[:12]}-{WORKER}.acct.workers.dev"
    assert result.upload_command_uncertain_but_readback_confirmed is False
    assert api.active == OLD
    assert len(calls) == 1
    joined = " ".join(calls[0])
    assert "versions upload" in joined
    assert "--preview-alias" in calls[0]
    assert f"FARE_COMMIT_SHA:{HEAD}" in calls[0]
    assert "FARE_DEPLOYMENT_MODE:PRODUCTION" in calls[0]


def test_lost_upload_response_is_confirmed_by_exact_version_delta():
    api = Api()
    calls = []

    def runner(args, **kwargs):
        calls.append(args)
        api.versions.add(NEW)
        return SimpleNamespace(returncode=1, stdout="", stderr="lost")

    result = mod.upload_version_candidate(
        runner=runner,
        api=api,
        worker_name=WORKER,
        head=HEAD,
        mode="PRODUCTION",
    )
    assert result.version_id == NEW
    assert result.upload_command_uncertain_but_readback_confirmed is True
    assert len(calls) == 1


def test_version_delta_fails_closed_on_zero_or_multiple():
    api = Api()
    with pytest.raises(mod.CloudflareReleaseError, match="WORKER_VERSION_UPLOAD_NOT_APPLIED"):
        mod._discover_single_new_version(api, WORKER, {OLD}, attempts=1, sleep=lambda _: None)
    api.versions.update({NEW, "33333333-3333-4333-8333-333333333333"})
    with pytest.raises(mod.CloudflareReleaseError, match="WORKER_VERSION_UPLOAD_PARTIAL_OR_AMBIGUOUS"):
        mod._discover_single_new_version(api, WORKER, {OLD}, attempts=1, sleep=lambda _: None)


def test_preview_urls_must_be_provider_enabled():
    api = Api()
    api.previews_enabled = False
    with pytest.raises(mod.CloudflareReleaseError, match="WORKER_PREVIEW_URLS_NOT_ENABLED"):
        mod.preview_alias_url(api, WORKER, "candidate")


def test_deploy_100_is_one_mutation_and_readback_first():
    api = Api()
    api.versions.add(NEW)
    calls = []

    def runner(args, **kwargs):
        calls.append(args)
        api.activate(NEW)
        return SimpleNamespace(returncode=1, stdout="", stderr="lost")

    result = mod.deploy_version_100(
        runner=runner,
        api=api,
        worker_name=WORKER,
        version_id=NEW,
        message="activate",
    )
    assert result.version_id == NEW
    assert result.command_uncertain_but_readback_confirmed is True
    assert len(calls) == 1
    assert f"{NEW}@100%" in calls[0]


def test_deploy_not_applied_is_not_retried():
    api = Api()
    api.versions.add(NEW)
    calls = []

    def runner(args, **kwargs):
        calls.append(args)
        return SimpleNamespace(returncode=1, stdout="", stderr="lost")

    with pytest.raises(mod.CloudflareReleaseError, match="WORKER_VERSION_DEPLOY_NOT_APPLIED"):
        mod.deploy_version_100(
            runner=runner,
            api=api,
            worker_name=WORKER,
            version_id=NEW,
            message="activate",
        )
    assert len(calls) == 1


def test_rollback_restores_exact_previous_version_without_resend():
    api = Api()
    api.versions.add(NEW)
    api.activate(NEW)
    calls = []

    def runner(args, **kwargs):
        calls.append(args)
        api.activate(OLD)
        return SimpleNamespace(returncode=1, stdout="", stderr="lost")

    result = mod.rollback_to_version(
        runner=runner,
        api=api,
        worker_name=WORKER,
        version_id=OLD,
        message="rollback",
    )
    assert api.active == OLD
    assert result.version_id == OLD
    assert result.command_uncertain_but_readback_confirmed is True
    assert len(calls) == 1


def test_rollback_skips_mutation_when_target_already_active():
    api = Api()
    calls = []
    result = mod.rollback_to_version(
        runner=lambda args, **kwargs: (calls.append(args) or SimpleNamespace(returncode=0)),
        api=api,
        worker_name=WORKER,
        version_id=OLD,
        message="rollback",
    )
    assert result.already_active is True
    assert calls == []
