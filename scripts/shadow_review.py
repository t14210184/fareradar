#!/usr/bin/env python3
"""Bounded Shadow-review transport with readback-first crash/retry safety."""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import pathlib
import secrets
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Iterable

ROOT = pathlib.Path(__file__).resolve().parents[1]
REQUIRED_FIELDS = {
    "sample_id", "subject_id", "subject_type", "observed_at", "label", "complex",
    "source_discovery", "agency_clearance", "false_actionable", "safety_error_code", "evidence_id",
}
SUBJECT_TYPES = {"ITINERARY", "PROMOTION", "AGENCY_OFFER", "SOURCE_EVENT", "EMAIL", "ROUTE"}
CANONICAL_ACCEPTANCE_FIELDS = {
    "pass", "commit_sha", "deployment_mode", "shadow_days", "labeled_candidates",
    "labeled_complex_candidates", "labeled_source_discovery_events", "labeled_agency_clearance_events",
    "complex_strategy_coverage", "complex_strategy_missing", "false_actionable_complex",
    "safety_critical_errors", "total_reviews",
}


class ShadowReviewError(RuntimeError):
    pass


class TransportUnknown(ShadowReviewError):
    pass


def evidence_root() -> pathlib.Path:
    raw = os.environ.get("FARE_EVIDENCE_ROOT", "")
    if not raw:
        return ROOT / "evidence"
    path = pathlib.Path(raw).expanduser()
    if not path.is_absolute():
        raise ShadowReviewError("FARE_EVIDENCE_ROOT_MUST_BE_ABSOLUTE")
    return path


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def local_head() -> str:
    head = git("rev-parse", "HEAD")
    if len(head) != 40:
        raise ShadowReviewError("LOCAL_HEAD_INVALID")
    return head


def require_clean_worktree() -> None:
    if git("status", "--porcelain"):
        raise ShadowReviewError("DIRTY_WORKTREE")


def load_reviews(path: pathlib.Path) -> list[dict[str, Any]]:
    reviews: list[dict[str, Any]] = []
    samples: set[str] = set()
    units: set[tuple[str, str, str]] = set()
    for line_no, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        try:
            review = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ShadowReviewError(f"INVALID_JSON_LINE:{line_no}") from exc
        if not isinstance(review, dict) or set(review) != REQUIRED_FIELDS:
            raise ShadowReviewError(f"INVALID_REVIEW_FIELDS:{line_no}")
        if review["subject_type"] not in SUBJECT_TYPES:
            raise ShadowReviewError(f"INVALID_SUBJECT_TYPE:{line_no}")
        for field in ("sample_id", "subject_id", "observed_at", "label", "evidence_id"):
            if not isinstance(review[field], str) or not review[field]:
                raise ShadowReviewError(f"INVALID_REVIEW_VALUE:{line_no}:{field}")
        for field in ("complex", "source_discovery", "agency_clearance", "false_actionable"):
            if type(review[field]) is not bool:
                raise ShadowReviewError(f"INVALID_REVIEW_VALUE:{line_no}:{field}")
        if review["safety_error_code"] is not None and (
            not isinstance(review["safety_error_code"], str) or not review["safety_error_code"].strip()
        ):
            raise ShadowReviewError(f"INVALID_REVIEW_VALUE:{line_no}:safety_error_code")
        sample = review["sample_id"]
        unit = (review["subject_type"], review["subject_id"], review["evidence_id"])
        if sample in samples:
            raise ShadowReviewError(f"DUPLICATE_SAMPLE_ID:{sample}")
        if unit in units:
            raise ShadowReviewError("DUPLICATE_REVIEW_UNIT:" + "|".join(unit))
        samples.add(sample)
        units.add(unit)
        reviews.append(review)
    if not reviews:
        raise ShadowReviewError("EMPTY_REVIEW_FILE")
    return reviews


def row_matches(row: dict[str, Any], review: dict[str, Any], key_id: str, commit: str) -> bool:
    expected = {
        "sample_id": review["sample_id"],
        "subject_type": review["subject_type"],
        "subject_id": review["subject_id"],
        "evidence_id": review["evidence_id"],
        "observed_at": review["observed_at"],
        "label": review["label"],
        "complex": 1 if review["complex"] else 0,
        "source_discovery": 1 if review["source_discovery"] else 0,
        "agency_clearance": 1 if review["agency_clearance"] else 0,
        "false_actionable": 1 if review["false_actionable"] else 0,
        "safety_error_code": review["safety_error_code"],
        "reviewer_key_id": key_id,
        "commit_sha": commit,
    }
    return all(row.get(k) == v for k, v in expected.items())


@dataclass
class SignedHttpTransport:
    base_url: str
    key_id: str
    secret: str
    timeout: float = 20.0

    def request(self, method: str, path: str, payload: dict[str, Any] | None = None, signed: bool = True) -> dict[str, Any]:
        body = "" if payload is None else json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
        url = self.base_url.rstrip("/") + path
        headers = {"accept": "application/json"}
        if body:
            headers["content-type"] = "application/json"
        if signed:
            ts = str(int(time.time() * 1000))
            nonce = secrets.token_urlsafe(24)
            body_hash = hashlib.sha256(body.encode()).hexdigest()
            canonical = "\n".join([self.key_id, ts, nonce, method.upper(), path, body_hash])
            signature = hmac.new(self.secret.encode(), canonical.encode(), hashlib.sha256).hexdigest()
            headers.update({
                "x-fare-key-id": self.key_id,
                "x-fare-timestamp": ts,
                "x-fare-nonce": nonce,
                "x-fare-signature": signature,
            })
        request = urllib.request.Request(url, data=body.encode() if body else None, headers=headers, method=method.upper())
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8")
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            try:
                detail = json.loads(raw)
            except Exception:
                detail = {"raw": raw}
            raise ShadowReviewError(f"HTTP_{exc.code}:{json.dumps(detail, sort_keys=True)}") from exc
        except (TimeoutError, urllib.error.URLError, ConnectionError) as exc:
            raise TransportUnknown("SHADOW_REVIEW_TRANSPORT_UNKNOWN") from exc


def _readback(transport: Any, review: dict[str, Any], key_id: str, commit: str) -> str:
    result = transport.request("POST", "/shadow/reviews/readback", {"sample_id": review["sample_id"]}, signed=True)
    row = result.get("review")
    if row is None:
        return "ABSENT"
    if isinstance(row, dict) and row_matches(row, review, key_id, commit):
        return "EXACT"
    return "MISMATCH"


def submit_reviews(
    reviews: Iterable[dict[str, Any]],
    *,
    transport: Any,
    key_id: str,
    commit: str,
    dry_run: bool = False,
) -> dict[str, Any]:
    health = transport.request("GET", "/health", None, signed=False)
    if health.get("spec") != "1.3" or health.get("deployment_mode") != "SHADOW_ACCEPTANCE" or health.get("commit_sha") != commit:
        raise ShadowReviewError("SHADOW_RUNTIME_IDENTITY_MISMATCH")
    items = list(reviews)
    if dry_run:
        return {"dry_run": True, "validated": len(items), "commit_sha": commit}
    confirmed = 0
    written = 0
    for review in items:
        before = _readback(transport, review, key_id, commit)
        if before == "EXACT":
            confirmed += 1
            continue
        if before != "ABSENT":
            raise ShadowReviewError(f"SHADOW_REVIEW_PREREADBACK_MISMATCH:{review['sample_id']}")
        try:
            transport.request("POST", "/shadow/reviews", review, signed=True)
        except TransportUnknown as exc:
            after_unknown = _readback(transport, review, key_id, commit)
            if after_unknown == "EXACT":
                confirmed += 1
                continue
            if after_unknown == "ABSENT":
                raise TransportUnknown(f"SHADOW_REVIEW_TRANSPORT_UNKNOWN_NOT_APPLIED:{review['sample_id']}") from exc
            raise ShadowReviewError(f"SHADOW_REVIEW_TRANSPORT_AMBIGUOUS:{review['sample_id']}") from exc
        after = _readback(transport, review, key_id, commit)
        if after != "EXACT":
            raise ShadowReviewError(f"SHADOW_REVIEW_POSTREADBACK_MISMATCH:{review['sample_id']}")
        written += 1
    acceptance = transport.request("POST", "/shadow/acceptance/readback", {}, signed=True)
    return {
        "dry_run": False,
        "validated": len(items),
        "written": written,
        "already_confirmed": confirmed,
        "commit_sha": commit,
        "acceptance": acceptance,
    }


def validate_acceptance(acceptance: Any, commit: str) -> dict[str, Any]:
    if not isinstance(acceptance, dict) or not CANONICAL_ACCEPTANCE_FIELDS <= set(acceptance):
        raise ShadowReviewError("SHADOW_ACCEPTANCE_SCHEMA_INVALID")
    if type(acceptance.get("pass")) is not bool:
        raise ShadowReviewError("SHADOW_ACCEPTANCE_SCHEMA_INVALID")
    if acceptance.get("commit_sha") != commit or acceptance.get("deployment_mode") != "SHADOW_ACCEPTANCE":
        raise ShadowReviewError("SHADOW_ACCEPTANCE_IDENTITY_MISMATCH")
    for field in (
        "shadow_days", "labeled_candidates", "labeled_complex_candidates",
        "labeled_source_discovery_events", "labeled_agency_clearance_events",
        "false_actionable_complex", "safety_critical_errors", "total_reviews",
    ):
        value = acceptance.get(field)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise ShadowReviewError("SHADOW_ACCEPTANCE_SCHEMA_INVALID")
    if not isinstance(acceptance.get("complex_strategy_coverage"), list) or not isinstance(acceptance.get("complex_strategy_missing"), list):
        raise ShadowReviewError("SHADOW_ACCEPTANCE_SCHEMA_INVALID")
    return acceptance


def write_acceptance_evidence(acceptance: Any, commit: str) -> pathlib.Path:
    canonical = validate_acceptance(acceptance, commit)
    path = evidence_root() / "shadow-acceptance.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(canonical, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def resolve_base_url(explicit: str | None) -> str:
    # Provider evidence is authoritative when available. The fallback is intentionally explicit.
    evidence = evidence_root() / "provider" / "worker-deploy.json"
    provider_url: str | None = None
    provider_head: str | None = None
    if evidence.exists():
        try:
            data = json.loads(evidence.read_text(encoding="utf-8"))
            provider_url = data.get("worker_origin") or data.get("base_url") or data.get("workers_dev_origin")
            provider_head = data.get("commit_sha") or data.get("head_sha")
        except Exception as exc:
            raise ShadowReviewError("CLOUDFLARE_PROVIDER_EVIDENCE_INVALID") from exc
        if not provider_url or provider_head != local_head():
            raise ShadowReviewError("CLOUDFLARE_PROVIDER_EVIDENCE_HEAD_MISMATCH")
    if provider_url and explicit and provider_url.rstrip("/") != explicit.rstrip("/"):
        raise ShadowReviewError("FARE_RADAR_BASE_URL_MISMATCH")
    result = provider_url or explicit
    if not result or not result.startswith("https://"):
        raise ShadowReviewError("FARE_RADAR_BASE_URL_REQUIRED")
    return result.rstrip("/")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=pathlib.Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    require_clean_worktree()
    reviews = load_reviews(args.input)
    key_id = os.environ.get("FARE_HMAC_KEY_ID", "")
    secret = os.environ.get("FARE_HMAC_SECRET", "")
    if not key_id or len(secret) < 16:
        raise ShadowReviewError("SHADOW_REVIEW_CREDENTIALS_REQUIRED")
    commit = local_head()
    base_url = resolve_base_url(os.environ.get("FARE_RADAR_BASE_URL"))
    result = submit_reviews(
        reviews,
        transport=SignedHttpTransport(base_url, key_id, secret),
        key_id=key_id,
        commit=commit,
        dry_run=args.dry_run,
    )
    if not args.dry_run:
        write_acceptance_evidence(result.get("acceptance"), commit)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ShadowReviewError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2)
