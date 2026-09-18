from __future__ import annotations

import json
import pathlib
import subprocess
import time
from dataclasses import dataclass
from typing import Any, Callable

import cloudflare_provider as cf

ROOT = pathlib.Path(__file__).resolve().parents[1]
WRANGLER = ["npx", "--yes", "wrangler@4.131.2"]


class CloudflareReleaseError(RuntimeError):
    pass


@dataclass(frozen=True)
class UploadedVersion:
    version_id: str
    preview_url: str
    upload_command_uncertain_but_readback_confirmed: bool


@dataclass(frozen=True)
class DeploymentChange:
    deployment_id: str
    version_id: str
    command_uncertain_but_readback_confirmed: bool
    already_active: bool = False


def _result(response: cf.Response, code: str) -> Any:
    if response.status != 200 or not isinstance(response.data, dict) or response.data.get("success") is not True:
        raise CloudflareReleaseError(code)
    return response.data.get("result")


def _run(runner: Callable[..., Any], args: list[str], *, timeout: int) -> Any:
    return runner(args, cwd=ROOT, text=True, capture_output=True, timeout=timeout, check=False)


def version_ids(api: Any, worker_name: str) -> set[str]:
    result = _result(
        api.get(f"/workers/scripts/{worker_name}/versions"),
        "WORKER_VERSIONS_READBACK_FAILED",
    )
    items = result.get("items") if isinstance(result, dict) else result
    if not isinstance(items, list):
        raise CloudflareReleaseError("WORKER_VERSIONS_READBACK_INVALID")
    return {
        str(item.get("id"))
        for item in items
        if isinstance(item, dict) and item.get("id")
    }


def active_single_version(api: Any, worker_name: str) -> tuple[str, str]:
    result = _result(
        api.get(f"/workers/scripts/{worker_name}/deployments"),
        "WORKER_DEPLOYMENTS_READBACK_FAILED",
    )
    try:
        deployment_id, versions = cf._deployment_versions(result)
    except cf.CloudflareProviderError as exc:
        raise CloudflareReleaseError(str(exc)) from exc
    return deployment_id, str(versions[0]["version_id"])


def preview_alias_url(api: Any, worker_name: str, alias: str) -> str:
    account = _result(api.get("/workers/subdomain"), "WORKERS_SUBDOMAIN_READBACK_FAILED")
    script = _result(
        api.get(f"/workers/scripts/{worker_name}/subdomain"),
        "WORKER_SUBDOMAIN_READBACK_FAILED",
    )
    subdomain = str(account.get("subdomain") or "") if isinstance(account, dict) else ""
    if (
        not subdomain
        or not isinstance(script, dict)
        or script.get("previews_enabled") is not True
    ):
        raise CloudflareReleaseError("WORKER_PREVIEW_URLS_NOT_ENABLED")
    return f"https://{alias}-{worker_name}.{subdomain}.workers.dev"


def _discover_single_new_version(
    api: Any,
    worker_name: str,
    before: set[str],
    *,
    attempts: int = 5,
    sleep: Callable[[float], None] = time.sleep,
) -> str:
    latest: set[str] = set()
    for attempt in range(attempts):
        latest = version_ids(api, worker_name)
        delta = latest - before
        if len(delta) == 1:
            return next(iter(delta))
        if len(delta) > 1:
            raise CloudflareReleaseError("WORKER_VERSION_UPLOAD_PARTIAL_OR_AMBIGUOUS")
        if attempt + 1 < attempts:
            sleep(1.0)
    raise CloudflareReleaseError("WORKER_VERSION_UPLOAD_NOT_APPLIED")


def upload_version_candidate(
    *,
    runner: Callable[..., Any],
    api: Any,
    worker_name: str,
    head: str,
    mode: str,
    config_path: str = "wrangler.jsonc",
    alias_prefix: str = "candidate",
) -> UploadedVersion:
    before = version_ids(api, worker_name)
    alias = f"{alias_prefix}-{head[:12]}".lower()
    tag = f"{mode.lower()}-{head[:16]}"
    command = [
        *WRANGLER,
        "versions",
        "upload",
        "--config",
        config_path,
        "--keep-vars",
        "--strict",
        "--preview-alias",
        alias,
        "--tag",
        tag,
        "--message",
        f"{mode} candidate {head}",
        "--var",
        f"FARE_COMMIT_SHA:{head}",
        "--var",
        f"FARE_DEPLOYMENT_MODE:{mode}",
    ]
    uncertain = False
    try:
        result = _run(runner, command, timeout=240)
        uncertain = getattr(result, "returncode", 1) != 0
    except subprocess.TimeoutExpired:
        uncertain = True
    version_id = _discover_single_new_version(api, worker_name, before)
    preview_url = preview_alias_url(api, worker_name, alias)
    return UploadedVersion(version_id, preview_url, uncertain)


def deploy_version_100(
    *,
    runner: Callable[..., Any],
    api: Any,
    worker_name: str,
    version_id: str,
    message: str,
) -> DeploymentChange:
    before_deployment, before_version = active_single_version(api, worker_name)
    if before_version == version_id:
        return DeploymentChange(before_deployment, version_id, False, True)
    command = [
        *WRANGLER,
        "versions",
        "deploy",
        f"{version_id}@100%",
        "-y",
        "--name",
        worker_name,
        "--message",
        message,
    ]
    uncertain = False
    try:
        result = _run(runner, command, timeout=180)
        uncertain = getattr(result, "returncode", 1) != 0
    except subprocess.TimeoutExpired:
        uncertain = True
    try:
        after_deployment, after_version = active_single_version(api, worker_name)
    except CloudflareReleaseError as exc:
        raise CloudflareReleaseError("WORKER_VERSION_DEPLOY_PARTIAL_OR_AMBIGUOUS") from exc
    if after_version == version_id:
        return DeploymentChange(after_deployment, version_id, uncertain, False)
    if after_version == before_version:
        raise CloudflareReleaseError("WORKER_VERSION_DEPLOY_NOT_APPLIED")
    raise CloudflareReleaseError("WORKER_VERSION_DEPLOY_PARTIAL_OR_AMBIGUOUS")


def rollback_to_version(
    *,
    runner: Callable[..., Any],
    api: Any,
    worker_name: str,
    version_id: str,
    message: str,
) -> DeploymentChange:
    try:
        before_deployment, before_version = active_single_version(api, worker_name)
    except CloudflareReleaseError:
        before_deployment, before_version = "", ""
    if before_version == version_id:
        return DeploymentChange(before_deployment, version_id, False, True)
    command = [
        *WRANGLER,
        "versions",
        "deploy",
        f"{version_id}@100%",
        "-y",
        "--name",
        worker_name,
        "--message",
        message,
    ]
    uncertain = False
    try:
        result = _run(runner, command, timeout=180)
        uncertain = getattr(result, "returncode", 1) != 0
    except subprocess.TimeoutExpired:
        uncertain = True
    try:
        after_deployment, after_version = active_single_version(api, worker_name)
    except CloudflareReleaseError as exc:
        raise CloudflareReleaseError("WORKER_ROLLBACK_PARTIAL_OR_AMBIGUOUS") from exc
    if after_version == version_id:
        return DeploymentChange(after_deployment, version_id, uncertain, False)
    raise CloudflareReleaseError("WORKER_ROLLBACK_PARTIAL_OR_AMBIGUOUS")
