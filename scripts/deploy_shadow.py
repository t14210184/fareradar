from __future__ import annotations

import json
import os
import pathlib
import re
import subprocess
from dataclasses import dataclass
from typing import Any, Callable

import cloudflare_provider as cf
import cloudflare_release as release
import live_probe
import production_preflight as preflight

ROOT = pathlib.Path(__file__).resolve().parents[1]
MODE = "SHADOW_ACCEPTANCE"


class ShadowDeployError(RuntimeError):
    pass


@dataclass(frozen=True)
class WorkerSnapshot:
    exists: bool
    commit_sha: str | None
    deployment_mode: str | None
    deployment_id: str | None
    version_id: str | None


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True, stderr=subprocess.DEVNULL).strip()


def local_head() -> str:
    head = git("rev-parse", "HEAD").lower()
    if not re.fullmatch(r"[0-9a-f]{40}", head):
        raise ShadowDeployError("LOCAL_HEAD_INVALID")
    return head


def require_clean_exact_head(expected: str) -> str:
    if git("status", "--porcelain"):
        raise ShadowDeployError("DIRTY_WORKTREE")
    head = local_head()
    if head != expected.lower():
        raise ShadowDeployError("SHADOW_EXPECTED_HEAD_MISMATCH")
    return head


def d1_id() -> str:
    text = (ROOT / "wrangler.jsonc").read_text(encoding="utf-8")
    match = re.search(r'"database_id"\s*:\s*"([^"]+)"', text)
    return match.group(1) if match else ""


def _result(response: cf.Response) -> Any:
    if response.status != 200 or not isinstance(response.data, dict) or response.data.get("success") is not True:
        return None
    return response.data.get("result")


def worker_snapshot(api: Any, worker_name: str) -> WorkerSnapshot:
    settings = _result(api.get(f"/workers/scripts/{worker_name}/settings"))
    deployments = _result(api.get(f"/workers/scripts/{worker_name}/deployments"))
    if settings is None and deployments is None:
        return WorkerSnapshot(False, None, None, None, None)
    if not isinstance(settings, dict) or deployments is None:
        return WorkerSnapshot(True, None, None, None, None)
    bindings = [item for item in (settings.get("bindings") or []) if isinstance(item, dict)]
    commit = cf._binding_value(bindings, "FARE_COMMIT_SHA")
    mode = cf._binding_value(bindings, "FARE_DEPLOYMENT_MODE")
    try:
        deployment_id, versions = cf._deployment_versions(deployments)
        version_id = str(versions[0]["version_id"])
    except cf.CloudflareProviderError:
        deployment_id = None
        version_id = None
    return WorkerSnapshot(
        True,
        str(commit) if commit is not None else None,
        str(mode) if mode is not None else None,
        deployment_id,
        version_id,
    )


def _run(runner: Callable[..., Any], args: list[str], *, timeout: int) -> Any:
    return runner(args, cwd=ROOT, text=True, capture_output=True, timeout=timeout, check=False)


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
        raise ShadowDeployError("SHADOW_DEPLOY_ENV_INCOMPLETE")
    return values


def _probe_kwargs(values: dict[str, str], *, base_url: str, head: str) -> dict[str, str]:
    return {
        "base_url": base_url,
        "expected_head": head,
        "expected_mode": MODE,
        "worker_token": values["FARE_WORKER_TOKEN"],
        "shadow_key_id": values["FARE_SHADOW_REVIEWER_KEY_ID"],
        "shadow_secret": values["FARE_SHADOW_REVIEWER_SECRET"],
        "access_key_id": values["FARE_ACCESS_REVIEWER_KEY_ID"],
        "access_secret": values["FARE_ACCESS_REVIEWER_SECRET"],
    }


def _rollback_existing_shadow(
    *,
    runner: Callable[..., Any],
    api: Any,
    worker_name: str,
    before: WorkerSnapshot,
    database_id: str,
    values: dict[str, str],
    probes: Callable[..., dict[str, Any]],
) -> dict[str, Any]:
    if (
        not before.version_id
        or not before.commit_sha
        or not re.fullmatch(r"[0-9a-f]{40}", before.commit_sha)
        or before.deployment_mode != MODE
    ):
        raise ShadowDeployError("SHADOW_ROLLBACK_PRESTATE_INVALID")
    try:
        change = release.rollback_to_version(
            runner=runner,
            api=api,
            worker_name=worker_name,
            version_id=before.version_id,
            message=f"automatic rollback to shadow {before.commit_sha}",
        )
        state = cf.collect_bootstrap_readback(
            api,
            account_id=values["CLOUDFLARE_ACCOUNT_ID"],
            database_id=database_id,
            worker_name=worker_name,
            expected_head=before.commit_sha,
            expected_mode=MODE,
        )
        probe_result = probes(
            **_probe_kwargs(values, base_url=state["worker_origin"], head=before.commit_sha)
        )
    except Exception as exc:
        raise ShadowDeployError("SHADOW_ROLLBACK_VALIDATION_FAILED") from exc
    return {
        "version_id": before.version_id,
        "deployment_id": change.deployment_id,
        "command_uncertain_but_readback_confirmed": change.command_uncertain_but_readback_confirmed,
        "already_active": change.already_active,
        "live_probes": probe_result,
    }


def _initial_bootstrap(
    *,
    runner: Callable[..., Any],
    api: Any,
    worker_name: str,
    head: str,
    database_id: str,
    values: dict[str, str],
    readback: Callable[..., dict[str, Any]],
    probes: Callable[..., dict[str, Any]],
) -> dict[str, Any]:
    command = [
        "npx",
        "--yes",
        "wrangler@4.131.2",
        "deploy",
        "--config",
        "wrangler.jsonc",
        "--keep-vars",
        "--strict",
        "--var",
        f"FARE_COMMIT_SHA:{head}",
        "--var",
        f"FARE_DEPLOYMENT_MODE:{MODE}",
    ]
    uncertain = False
    try:
        result = _run(runner, command, timeout=240)
        uncertain = getattr(result, "returncode", 1) != 0
    except subprocess.TimeoutExpired:
        uncertain = True
    try:
        state = readback(
            api,
            account_id=values["CLOUDFLARE_ACCOUNT_ID"],
            database_id=database_id,
            worker_name=worker_name,
            expected_head=head,
            expected_mode=MODE,
        )
    except cf.CloudflareProviderError as exc:
        after = worker_snapshot(api, worker_name)
        if not after.exists:
            raise ShadowDeployError("SHADOW_DEPLOY_NOT_APPLIED") from exc
        raise ShadowDeployError("SHADOW_DEPLOY_PARTIAL_OR_AMBIGUOUS") from exc
    probe_result = probes(**_probe_kwargs(values, base_url=state["worker_origin"], head=head))
    cf.write_bootstrap_evidence(state)
    return {
        "ok": True,
        "commit_sha": head,
        "deployment_mode": MODE,
        "version_id": state["version_id"],
        "deploy_strategy": "INITIAL_BOOTSTRAP",
        "deploy_command_uncertain_but_readback_confirmed": uncertain,
        "live_probes": probe_result,
        "provider_readback_stage": "BOOTSTRAP_ONLY",
        "next_gate": "HUMAN_ACCESS_REVIEW_THEN_FULL_CLOUDFLARE_READBACK",
    }


def _versioned_shadow_update(
    *,
    runner: Callable[..., Any],
    api: Any,
    worker_name: str,
    head: str,
    database_id: str,
    values: dict[str, str],
    before: WorkerSnapshot,
    readback: Callable[..., dict[str, Any]],
    probes: Callable[..., dict[str, Any]],
) -> dict[str, Any]:
    if (
        before.deployment_mode != MODE
        or not before.version_id
        or not before.commit_sha
        or not re.fullmatch(r"[0-9a-f]{40}", before.commit_sha)
    ):
        raise ShadowDeployError("SHADOW_EXISTING_PRESTATE_NOT_SAFE")
    try:
        candidate = release.upload_version_candidate(
            runner=runner,
            api=api,
            worker_name=worker_name,
            head=head,
            mode=MODE,
            alias_prefix="shadow",
        )
    except release.CloudflareReleaseError as exc:
        raise ShadowDeployError(f"SHADOW_VERSION_UPLOAD_FAILED:{exc}") from exc
    try:
        preview_probe = probes(**_probe_kwargs(values, base_url=candidate.preview_url, head=head))
    except Exception as exc:
        raise ShadowDeployError("SHADOW_PREVIEW_VALIDATION_FAILED") from exc
    try:
        activation = release.deploy_version_100(
            runner=runner,
            api=api,
            worker_name=worker_name,
            version_id=candidate.version_id,
            message=f"activate shadow {head}",
        )
    except release.CloudflareReleaseError as exc:
        rollback = _rollback_existing_shadow(
            runner=runner,
            api=api,
            worker_name=worker_name,
            before=before,
            database_id=database_id,
            values=values,
            probes=probes,
        )
        error = ShadowDeployError(f"SHADOW_VERSION_ACTIVATION_FAILED_ROLLED_BACK:{exc}")
        setattr(error, "rollback", rollback)
        raise error from exc
    try:
        state = readback(
            api,
            account_id=values["CLOUDFLARE_ACCOUNT_ID"],
            database_id=database_id,
            worker_name=worker_name,
            expected_head=head,
            expected_mode=MODE,
        )
        post_probe = probes(**_probe_kwargs(values, base_url=state["worker_origin"], head=head))
        cf.write_bootstrap_evidence(state)
    except Exception as exc:
        rollback = _rollback_existing_shadow(
            runner=runner,
            api=api,
            worker_name=worker_name,
            before=before,
            database_id=database_id,
            values=values,
            probes=probes,
        )
        error = ShadowDeployError("SHADOW_POSTDEPLOY_VALIDATION_FAILED_ROLLED_BACK")
        setattr(error, "rollback", rollback)
        raise error from exc
    return {
        "ok": True,
        "commit_sha": head,
        "deployment_mode": MODE,
        "previous_shadow_commit_sha": before.commit_sha,
        "previous_shadow_version_id": before.version_id,
        "candidate_version_id": candidate.version_id,
        "preview_url": candidate.preview_url,
        "preview_live_probes": preview_probe,
        "upload_command_uncertain_but_readback_confirmed": candidate.upload_command_uncertain_but_readback_confirmed,
        "deployment_id": activation.deployment_id,
        "version_id": state["version_id"],
        "deploy_strategy": "VERSIONED_SHADOW_UPDATE",
        "deploy_command_uncertain_but_readback_confirmed": activation.command_uncertain_but_readback_confirmed,
        "live_probes": post_probe,
        "provider_readback_stage": "BOOTSTRAP_ONLY",
        "next_gate": "HUMAN_ACCESS_REVIEW_THEN_FULL_CLOUDFLARE_READBACK",
    }


def deploy_shadow(
    *,
    runner: Callable[..., Any] = subprocess.run,
    api_factory: Callable[[str, str], Any] = cf.CloudflareApi,
    readback: Callable[..., dict[str, Any]] = cf.collect_bootstrap_readback,
    probes: Callable[..., dict[str, Any]] = live_probe.run_probes,
) -> dict[str, Any]:
    expected = os.environ.get("FARE_SHADOW_EXPECTED_HEAD", "").lower()
    if not re.fullmatch(r"[0-9a-f]{40}", expected):
        raise ShadowDeployError("FARE_SHADOW_EXPECTED_HEAD_REQUIRED")
    head = require_clean_exact_head(expected)
    if not preflight.code_ready(head):
        raise ShadowDeployError("LOCAL_CODE_GATES_NOT_READY")
    configured_d1 = d1_id()
    if configured_d1 in preflight.PLACEHOLDERS:
        raise ShadowDeployError("D1_DATABASE_ID_MISSING")
    values = _required_env()
    if values["FARE_D1_DATABASE_ID"] != configured_d1:
        raise ShadowDeployError("D1_DATABASE_ID_ENV_MISMATCH")
    worker_name = os.environ.get("FARE_CLOUDFLARE_WORKER_NAME", "fare-radar")

    build = _run(runner, ["npm", "run", "build"], timeout=180)
    if getattr(build, "returncode", 1) != 0:
        raise ShadowDeployError("SHADOW_BUILD_FAILED")

    api = api_factory(values["CLOUDFLARE_ACCOUNT_ID"], values["CLOUDFLARE_API_TOKEN"])
    before = worker_snapshot(api, worker_name)
    if not before.exists:
        return _initial_bootstrap(
            runner=runner,
            api=api,
            worker_name=worker_name,
            head=head,
            database_id=configured_d1,
            values=values,
            readback=readback,
            probes=probes,
        )
    return _versioned_shadow_update(
        runner=runner,
        api=api,
        worker_name=worker_name,
        head=head,
        database_id=configured_d1,
        values=values,
        before=before,
        readback=readback,
        probes=probes,
    )


def main() -> int:
    try:
        result = deploy_shadow()
        print(json.dumps(result, sort_keys=True))
        return 0
    except ShadowDeployError as exc:
        payload: dict[str, Any] = {"ok": False, "error": str(exc)}
        rollback = getattr(exc, "rollback", None)
        if rollback is not None:
            payload["rollback"] = rollback
        print(json.dumps(payload, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
