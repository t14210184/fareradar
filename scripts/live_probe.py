from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import secrets
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


class LiveProbeError(RuntimeError):
    pass


@dataclass
class HttpResult:
    status: int
    data: Any


def _request(url: str, *, method: str = "GET", payload: dict[str, Any] | None = None, headers: dict[str, str] | None = None, timeout: float = 20.0) -> HttpResult:
    body = b"" if payload is None else json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode()
    req_headers = {"accept": "application/json", **(headers or {})}
    if body:
        req_headers["content-type"] = "application/json"
    req = urllib.request.Request(url, data=body or None, headers=req_headers, method=method.upper())
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
            return HttpResult(response.status, json.loads(raw) if raw else {})
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            data = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            data = {"raw": raw}
        return HttpResult(exc.code, data)
    except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as exc:
        raise LiveProbeError("LIVE_PROBE_TRANSPORT_UNKNOWN") from exc


def _signed_headers(key_id: str, secret: str, method: str, path: str, body: str) -> dict[str, str]:
    ts = str(int(time.time() * 1000))
    nonce = secrets.token_urlsafe(24)
    body_hash = hashlib.sha256(body.encode()).hexdigest()
    canonical = "\n".join([key_id, ts, nonce, method.upper(), path, body_hash])
    signature = hmac.new(secret.encode(), canonical.encode(), hashlib.sha256).hexdigest()
    return {"x-fare-key-id": key_id, "x-fare-timestamp": ts, "x-fare-nonce": nonce, "x-fare-signature": signature}


def verify_runtime(base_url: str, expected_head: str, expected_mode: str) -> dict[str, Any]:
    result = _request(base_url.rstrip("/") + "/health")
    data = result.data if isinstance(result.data, dict) else {}
    if result.status != 200 or data.get("spec") != "1.3" or data.get("commit_sha") != expected_head or data.get("deployment_mode") != expected_mode:
        raise LiveProbeError("LIVE_PROBE_RUNTIME_IDENTITY_MISMATCH")
    return data


def probe_worker_token(base_url: str, token: str) -> None:
    payload = {"job_id": "probe-missing-job", "worker_id": "probe-worker", "source_id": "probe-source", "success": False}
    result = _request(base_url.rstrip("/") + "/verification-jobs/complete", method="POST", payload=payload, headers={"x-fare-worker-token": token})
    if result.status == 401:
        raise LiveProbeError("WORKER_TOKEN_PROBE_UNAUTHORIZED")
    if result.status != 403 or not isinstance(result.data, dict) or result.data.get("error") != "LIVE_SOURCE_LEASE_REQUIRED":
        raise LiveProbeError("WORKER_TOKEN_PROBE_UNEXPECTED_RESULT")


def probe_reviewer(base_url: str, *, key_id: str, secret: str, role: str) -> None:
    if role == "SHADOW_REVIEWER":
        path = "/shadow/reviews/readback"
        payload = {"sample_id": "probe-missing-sample"}
        expected_key = "review"
    elif role == "ACCESS_REVIEWER":
        path = "/audit/evidence/readback"
        payload = {"evidence_id": "probe-missing-evidence"}
        expected_key = "evidence"
    else:
        raise LiveProbeError("LIVE_PROBE_ROLE_INVALID")
    body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
    headers = _signed_headers(key_id, secret, "POST", path, body)
    result = _request(base_url.rstrip("/") + path, method="POST", payload=payload, headers=headers)
    if result.status == 401:
        raise LiveProbeError(f"{role}_PROBE_UNAUTHORIZED")
    if result.status != 200 or not isinstance(result.data, dict) or result.data.get(expected_key) is not None:
        raise LiveProbeError(f"{role}_PROBE_UNEXPECTED_RESULT")


def run_probes(*, base_url: str, expected_head: str, expected_mode: str, worker_token: str, shadow_key_id: str, shadow_secret: str, access_key_id: str, access_secret: str) -> dict[str, Any]:
    health = verify_runtime(base_url, expected_head, expected_mode)
    probe_worker_token(base_url, worker_token)
    probe_reviewer(base_url, key_id=shadow_key_id, secret=shadow_secret, role="SHADOW_REVIEWER")
    probe_reviewer(base_url, key_id=access_key_id, secret=access_secret, role="ACCESS_REVIEWER")
    return {"ok": True, "commit_sha": expected_head, "deployment_mode": expected_mode, "worker_token_probe": True, "shadow_reviewer_probe": True, "access_reviewer_probe": True, "runtime": health}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=os.environ.get("FARE_WORKER_ORIGIN", ""))
    parser.add_argument("--expected-head", default=os.environ.get("FARE_COMMIT_SHA", ""))
    parser.add_argument("--expected-mode", default=os.environ.get("FARE_DEPLOYMENT_MODE", ""))
    args = parser.parse_args()
    values = {
        "worker_token": os.environ.get("FARE_WORKER_TOKEN", ""),
        "shadow_key_id": os.environ.get("FARE_SHADOW_REVIEWER_KEY_ID", ""),
        "shadow_secret": os.environ.get("FARE_SHADOW_REVIEWER_SECRET", ""),
        "access_key_id": os.environ.get("FARE_ACCESS_REVIEWER_KEY_ID", ""),
        "access_secret": os.environ.get("FARE_ACCESS_REVIEWER_SECRET", ""),
    }
    if not args.base_url.startswith("https://") or len(args.expected_head) != 40 or not args.expected_mode or not all(values.values()):
        print(json.dumps({"ok": False, "error": "LIVE_PROBE_ENV_INCOMPLETE"}, sort_keys=True))
        return 2
    try:
        result = run_probes(base_url=args.base_url, expected_head=args.expected_head, expected_mode=args.expected_mode, **values)
        print(json.dumps(result, sort_keys=True))
        return 0
    except LiveProbeError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
