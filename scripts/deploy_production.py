from __future__ import annotations

import json
import os
import re
import subprocess
from typing import Any, Callable

import cloudflare_provider as cf
import deploy_shadow as shadow
import live_probe
import production_preflight as preflight

MODE = "PRODUCTION"


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
        "CLOUDFLARE_API_TOKEN", "CLOUDFLARE_ACCOUNT_ID", "FARE_D1_DATABASE_ID",
        "FARE_WORKER_TOKEN", "FARE_SHADOW_REVIEWER_KEY_ID", "FARE_SHADOW_REVIEWER_SECRET",
        "FARE_ACCESS_REVIEWER_KEY_ID", "FARE_ACCESS_REVIEWER_SECRET",
    ]
    values = {name: os.environ.get(name, "") for name in names}
    if not all(values.values()):
        raise ProductionDeployError("PRODUCTION_DEPLOY_ENV_INCOMPLETE")
    return values


def deploy_production(*, runner: Callable[..., Any] = subprocess.run, api_factory: Callable[[str, str], Any] = cf.CloudflareApi, readback: Callable[..., dict[str, Any]] = cf.collect_readback, probes: Callable[..., dict[str, Any]] = live_probe.run_probes) -> dict[str, Any]:
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
    if not before.exists or before.commit_sha != head or before.deployment_mode != "SHADOW_ACCEPTANCE":
        raise ProductionDeployError("PRODUCTION_PRESTATE_NOT_EXACT_SHADOW")

    command = [
        "npx", "--yes", "wrangler@4.131.2", "deploy", "--config", "wrangler.jsonc",
        "--keep-vars", "--strict",
        "--var", f"FARE_COMMIT_SHA:{head}",
        "--var", "FARE_DEPLOYMENT_MODE:PRODUCTION",
    ]
    deploy_unknown = False
    try:
        result = shadow._run(runner, command, timeout=240)
        deploy_unknown = getattr(result, "returncode", 1) != 0
    except subprocess.TimeoutExpired:
        deploy_unknown = True

    try:
        state = readback(api, account_id=values["CLOUDFLARE_ACCOUNT_ID"], database_id=configured_d1, worker_name=worker_name, expected_head=head, expected_mode=MODE)
    except cf.CloudflareProviderError as exc:
        after = shadow.worker_snapshot(api, worker_name)
        if after == before:
            raise ProductionDeployError("PRODUCTION_DEPLOY_NOT_APPLIED") from exc
        raise ProductionDeployError("PRODUCTION_DEPLOY_PARTIAL_OR_AMBIGUOUS") from exc

    probe_result = probes(
        base_url=state["worker_origin"], expected_head=head, expected_mode=MODE,
        worker_token=values["FARE_WORKER_TOKEN"],
        shadow_key_id=values["FARE_SHADOW_REVIEWER_KEY_ID"], shadow_secret=values["FARE_SHADOW_REVIEWER_SECRET"],
        access_key_id=values["FARE_ACCESS_REVIEWER_KEY_ID"], access_secret=values["FARE_ACCESS_REVIEWER_SECRET"],
    )
    cf.write_evidence(state)
    return {
        "ok": True, "commit_sha": head, "deployment_mode": MODE, "version_id": state["version_id"],
        "deploy_command_uncertain_but_readback_confirmed": deploy_unknown, "live_probes": probe_result,
    }


def main() -> int:
    try:
        result = deploy_production()
        print(json.dumps(result, sort_keys=True))
        return 0
    except ProductionDeployError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
