from __future__ import annotations

import json
import os
import re
import subprocess
from typing import Any, Callable

import cloudflare_provider as cf
import cloudflare_release as release
import deploy_shadow as shadow
import live_probe
import production_preflight as preflight

MODE = "PRODUCTION"
SHADOW_MODE = "SHADOW_ACCEPTANCE"


class ProductionDeployError(RuntimeError):
    pass


def require_human_approved_exact_head() -> str:
    approved = os.environ.get("FARE_PRODUCTION_HUMAN_APPROVED_HEAD", "").lower()
    if not re.fullmatch(r"[0-9a-f]{40}", approved):
        raise ProductionDeployError("PRODUCTION_HUMAN_APPROVAL_REQUIRED")
    if shadow.git("status", "--porcelain"):
        raise ProductionDeployError("DIRTY_WORKTREE")
    head = shadow.local_head()
    if approved != head:
        raise ProductionDeployError("PRODUCTION_HUMAN_APPROVAL_HEAD_MISMATCH")
    return head


def _required_env() -> dict[str, str]:
    names = [
        "CLOUDFLARE_API_TOKEN",
        "CLOUDFLARE_ACCOUNT_ID",
        "FARE_D1_DATABASE_ID",
        "FARE_WORKER_TOKEN",
        "FARE_SHADOW_REVIEWER_KEY_ID",
        "FARE_SHADOW_REVIEWER_SECRET",
        "FARE_ACCESS_REVIEWER_KEY_ID",
        "FARE_ACCESS_REVIEWER_SECRET",
    ]
    values = {name: os.environ.get(name, "") for name in names}
    if not all(values.values()):
        raise ProductionDeployError("PRODUCTION_DEPLOY_ENV_INCOMPLETE")
    return values


def _probe_kwargs(values: dict[str, str], *, base_url: str, head: str, mode: str) -> dict[str, str]:
    return {
        "base_url": base_url,
        "expected_head": head,
        "expected_mode": mode,
        "worker_token": values["FARE_WORKER_TOKEN"],
        "shadow_key_id": values["FARE_SHADOW_REVIEWER_KEY_ID"],
        "shadow_secret": values["FARE_SHADOW_REVIEWER_SECRET"],
        "access_key_id": values["FARE_ACCESS_REVIEWER_KEY_ID"],
        "access_secret": values["FARE_ACCESS_REVIEWER_SECRET"],
    }


def _rollback_and_verify(
    *,
    runner: Callable[..., Any],
    api: Any,
    worker_name: str,
    previous_version_id: str,
    head: str,
    database_id: str,
    values: dict[str, str],
    probes: Callable[..., dict[str, Any]],
) -> dict[str, Any]:
    try:
        change = release.rollback_to_version(
            runner=runner,
            api=api,
            worker_name=worker_name,
            version_id=previous_version_id,
            message=f"automatic rollback to shadow {head}",
        )
    except release.CloudflareReleaseError as exc:
        raise ProductionDeployError(f"PRODUCTION_ROLLBACK_FAILED:{exc}") from exc
    try:
        state = cf.collect_bootstrap_readback(
            api,
            account_id=values["CLOUDFLARE_ACCOUNT_ID"],
            database_id=database_id,
            worker_name=worker_name,
            expected_head=head,
            expected_mode=SHADOW_MODE,
        )
        probe_result = probes(
            **_probe_kwargs(values, base_url=state["worker_origin"], head=head, mode=SHADOW_MODE)
        )
    except Exception as exc:
        raise ProductionDeployError("PRODUCTION_ROLLBACK_VALIDATION_FAILED") from exc
    return {
        "version_id": previous_version_id,
        "deployment_id": change.deployment_id,
        "command_uncertain_but_readback_confirmed": change.command_uncertain_but_readback_confirmed,
        "already_active": change.already_active,
        "live_probes": probe_result,
    }


def deploy_production(
    *,
    runner: Callable[..., Any] = subprocess.run,
    api_factory: Callable[[str, str], Any] = cf.CloudflareApi,
    readback: Callable[..., dict[str, Any]] = cf.collect_readback,
    probes: Callable[..., dict[str, Any]] = live_probe.run_probes,
) -> dict[str, Any]:
    head = require_human_approved_exact_head()
    current = preflight.evaluate()
    if current.get("blockers") != ["PRODUCTION_ACTIVATION_REQUIRED"]:
        raise ProductionDeployError("PRODUCTION_PREREQUISITES_NOT_SATISFIED")

    configured_d1 = shadow.d1_id()
    values = _required_env()
    if configured_d1 in preflight.PLACEHOLDERS or values["FARE_D1_DATABASE_ID"] != configured_d1:
        raise ProductionDeployError("PRODUCTION_D1_IDENTITY_MISMATCH")
    worker_name = os.environ.get("FARE_CLOUDFLARE_WORKER_NAME", "fare-radar")

    build = shadow._run(runner, ["npm", "run", "build"], timeout=180)
    if getattr(build, "returncode", 1) != 0:
        raise ProductionDeployError("PRODUCTION_BUILD_FAILED")

    api = api_factory(values["CLOUDFLARE_ACCOUNT_ID"], values["CLOUDFLARE_API_TOKEN"])
    before = shadow.worker_snapshot(api, worker_name)
    if (
        not before.exists
        or before.commit_sha != head
        or before.deployment_mode != SHADOW_MODE
        or not before.version_id
    ):
        raise ProductionDeployError("PRODUCTION_PRESTATE_NOT_EXACT_SHADOW")

    try:
        candidate = release.upload_version_candidate(
            runner=runner,
            api=api,
            worker_name=worker_name,
            head=head,
            mode=MODE,
            alias_prefix="prod",
        )
    except release.CloudflareReleaseError as exc:
        raise ProductionDeployError(f"PRODUCTION_VERSION_UPLOAD_FAILED:{exc}") from exc

    try:
        preview_probe = probes(
            **_probe_kwargs(values, base_url=candidate.preview_url, head=head, mode=MODE)
        )
    except Exception as exc:
        raise ProductionDeployError("PRODUCTION_PREVIEW_VALIDATION_FAILED") from exc

    try:
        activation = release.deploy_version_100(
            runner=runner,
            api=api,
            worker_name=worker_name,
            version_id=candidate.version_id,
            message=f"activate production {head}",
        )
    except release.CloudflareReleaseError as exc:
        rollback = _rollback_and_verify(
            runner=runner,
            api=api,
            worker_name=worker_name,
            previous_version_id=before.version_id,
            head=head,
            database_id=configured_d1,
            values=values,
            probes=probes,
        )
        error = ProductionDeployError(f"PRODUCTION_VERSION_ACTIVATION_FAILED_ROLLED_BACK:{exc}")
        setattr(error, "rollback", rollback)
        raise error from exc

    try:
        state = readback(
            api,
            account_id=values["CLOUDFLARE_ACCOUNT_ID"],
            database_id=configured_d1,
            worker_name=worker_name,
            expected_head=head,
            expected_mode=MODE,
        )
        post_probe = probes(
            **_probe_kwargs(values, base_url=state["worker_origin"], head=head, mode=MODE)
        )
        cf.write_evidence(state)
    except Exception as exc:
        rollback = _rollback_and_verify(
            runner=runner,
            api=api,
            worker_name=worker_name,
            previous_version_id=before.version_id,
            head=head,
            database_id=configured_d1,
            values=values,
            probes=probes,
        )
        error = ProductionDeployError("PRODUCTION_POSTDEPLOY_VALIDATION_FAILED_ROLLED_BACK")
        setattr(error, "rollback", rollback)
        raise error from exc

    return {
        "ok": True,
        "commit_sha": head,
        "deployment_mode": MODE,
        "previous_shadow_version_id": before.version_id,
        "candidate_version_id": candidate.version_id,
        "preview_url": candidate.preview_url,
        "preview_live_probes": preview_probe,
        "upload_command_uncertain_but_readback_confirmed": candidate.upload_command_uncertain_but_readback_confirmed,
        "deployment_id": activation.deployment_id,
        "version_id": state["version_id"],
        "deploy_command_uncertain_but_readback_confirmed": activation.command_uncertain_but_readback_confirmed,
        "live_probes": post_probe,
        "rollback_boundary": "WORKER_VERSION_ONLY_D1_NOT_ROLLED_BACK",
    }


def main() -> int:
    try:
        result = deploy_production()
        print(json.dumps(result, sort_keys=True))
        return 0
    except ProductionDeployError as exc:
        payload: dict[str, Any] = {"ok": False, "error": str(exc)}
        rollback = getattr(exc, "rollback", None)
        if rollback is not None:
            payload["rollback"] = rollback
        print(json.dumps(payload, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
