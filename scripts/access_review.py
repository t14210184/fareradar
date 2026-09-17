from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import hmac
import json
import os
import pathlib
import secrets
import socket
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable

ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCE_FIELDS = (
    "review_id", "source_id", "target_state", "access_basis", "terms_snapshot_at", "evidence_id",
    "access_basis_valid", "privacy_review_pass", "parser_contract_pass", "provenance_hash_pass",
    "rate_budget_pass", "shadow_pass",
)
PROVIDER_FIELDS = (
    "review_id", "provider_id", "access_basis", "terms_snapshot_at", "rate_policy", "evidence_id",
    "access_basis_valid", "terms_review_pass", "rate_policy_review_pass",
)
PROVIDER_ACCESS_BASES = {"OFFICIAL_API", "PARTNER_CONTRACT", "AIRLINE_DIRECT", "MANUAL_ORACLE", "PUBLIC_PAGE_MONITOR"}
ALLOWED_MODES = {"SHADOW_ACCEPTANCE", "PRODUCTION"}


class AccessReviewError(RuntimeError):
    pass


class TransportUnknown(AccessReviewError):
    pass


def _compact(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _git_head() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip().lower()


def _require_clean() -> None:
    if subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip():
        raise AccessReviewError("ACCESS_REVIEW_DIRTY_WORKTREE")


def _iso(value: Any) -> bool:
    if not isinstance(value, str) or value == "RECHECK_REQUIRED":
        return False
    try:
        return dt.datetime.fromisoformat(value.replace("Z", "+00:00")).tzinfo is not None
    except ValueError:
        return False


def _required_bool(review: dict[str, Any], name: str) -> None:
    if type(review.get(name)) is not bool:
        raise AccessReviewError(f"ACCESS_REVIEW_FIELD_INVALID:{name}")


def validate_record(record: Any) -> dict[str, Any]:
    if not isinstance(record, dict) or set(record) != {"kind", "review"}:
        raise AccessReviewError("ACCESS_REVIEW_WRAPPER_FIELDS_INVALID")
    kind = record.get("kind")
    review = record.get("review")
    if kind not in {"source", "provider"} or not isinstance(review, dict):
        raise AccessReviewError("ACCESS_REVIEW_KIND_INVALID")
    expected = SOURCE_FIELDS if kind == "source" else PROVIDER_FIELDS
    if set(review) != set(expected):
        raise AccessReviewError("ACCESS_REVIEW_FIELDS_INVALID")
    for name in ("review_id", "evidence_id", "terms_snapshot_at"):
        if not isinstance(review.get(name), str) or not review[name]:
            raise AccessReviewError(f"ACCESS_REVIEW_FIELD_INVALID:{name}")
    entity_key = "source_id" if kind == "source" else "provider_id"
    if not isinstance(review.get(entity_key), str) or not review[entity_key]:
        raise AccessReviewError(f"ACCESS_REVIEW_FIELD_INVALID:{entity_key}")
    if not _iso(review["terms_snapshot_at"]):
        raise AccessReviewError("ACCESS_REVIEW_TERMS_TIMESTAMP_INVALID")
    if kind == "source":
        if review["target_state"] not in {"SHADOW", "ENABLED"}:
            raise AccessReviewError("ACCESS_REVIEW_TARGET_STATE_INVALID")
        if not isinstance(review["access_basis"], str) or not review["access_basis"].strip():
            raise AccessReviewError("ACCESS_REVIEW_ACCESS_BASIS_INVALID")
        for name in SOURCE_FIELDS[-6:]:
            _required_bool(review, name)
    else:
        if review["access_basis"] not in PROVIDER_ACCESS_BASES:
            raise AccessReviewError("ACCESS_REVIEW_ACCESS_BASIS_INVALID")
        if not isinstance(review["rate_policy"], str) or not review["rate_policy"].strip():
            raise AccessReviewError("ACCESS_REVIEW_RATE_POLICY_INVALID")
        for name in PROVIDER_FIELDS[-3:]:
            _required_bool(review, name)
    return {"kind": kind, "review": {name: review[name] for name in expected}}


def load_jsonl(path: pathlib.Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    seen_reviews: set[str] = set()
    seen_evidence: set[str] = set()
    for line_no, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        try:
            record = validate_record(json.loads(raw))
        except json.JSONDecodeError as exc:
            raise AccessReviewError(f"ACCESS_REVIEW_JSON_INVALID:{line_no}") from exc
        review = record["review"]
        if review["review_id"] in seen_reviews:
            raise AccessReviewError(f"ACCESS_REVIEW_DUPLICATE_REVIEW_ID:{review['review_id']}")
        if review["evidence_id"] in seen_evidence:
            raise AccessReviewError(f"ACCESS_REVIEW_DUPLICATE_EVIDENCE_ID:{review['evidence_id']}")
        seen_reviews.add(review["review_id"])
        seen_evidence.add(review["evidence_id"])
        records.append(record)
    if not records:
        raise AccessReviewError("ACCESS_REVIEW_INPUT_EMPTY")
    return records


def review_payload_hash(record: dict[str, Any]) -> str:
    return _sha256_text(_compact(record["review"]))


def _provider_origin_from(data: dict[str, Any]) -> str | None:
    candidates = [data.get("worker_origin"), data.get("base_url"), data.get("origin"), data.get("workers_dev_origin")]
    nested = data.get("provider_readback")
    if isinstance(nested, dict):
        candidates += [nested.get("worker_origin"), nested.get("base_url"), nested.get("origin"), nested.get("workers_dev_origin")]
    for value in candidates:
        if isinstance(value, str) and value.startswith("https://"):
            return value.rstrip("/")
    return None


def resolve_base_url(head: str, explicit: str | None = None, provider_path: pathlib.Path | None = None) -> str:
    provider_path = provider_path or ROOT / "evidence" / "provider" / "worker-deploy.json"
    evidence = None
    if provider_path.exists():
        try:
            evidence = json.loads(provider_path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise AccessReviewError("ACCESS_REVIEW_PROVIDER_EVIDENCE_INVALID") from exc
    explicit = explicit.rstrip("/") if explicit else None
    if evidence is not None:
        if evidence.get("commit_sha") != head:
            raise AccessReviewError("ACCESS_REVIEW_PROVIDER_HEAD_MISMATCH")
        origin = _provider_origin_from(evidence)
        if not origin:
            raise AccessReviewError("ACCESS_REVIEW_PROVIDER_ORIGIN_MISSING")
        if explicit and explicit != origin:
            raise AccessReviewError("ACCESS_REVIEW_BASE_URL_MISMATCH")
        return origin
    if not explicit or not explicit.startswith("https://"):
        raise AccessReviewError("ACCESS_REVIEW_BASE_URL_REQUIRED")
    return explicit


def evidence_for(record: dict[str, Any], head: str, created_at: str | None = None) -> dict[str, Any]:
    kind = record["kind"]
    review = record["review"]
    entity_key = "source_id" if kind == "source" else "provider_id"
    payload_hash = review_payload_hash(record)
    created_at = created_at or dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")
    return {
        "evidence_id": review["evidence_id"],
        "gate_id": "TERMS_AND_PRIVACY_REVIEW" if kind == "source" else "ACCESS_BASIS_REVIEW",
        "spec_version": "1.3",
        "commit_sha": head,
        "test_report_hash": payload_hash,
        "provider_readback": {"access_review": {
            "kind": kind,
            "entity_id": review[entity_key],
            "review_id": review["review_id"],
            "human_review_payload_sha256": payload_hash,
        }},
        "unresolved_items": [],
        "created_at": created_at,
    }


@dataclass
class HttpResult:
    status: int
    data: Any


class SignedHttpTransport:
    def __init__(self, base_url: str, key_id: str, secret: str, timeout: float = 15.0):
        self.base_url = base_url.rstrip("/")
        self.key_id = key_id
        self.secret = secret
        self.timeout = timeout

    def _open(self, request: urllib.request.Request) -> HttpResult:
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8")
                return HttpResult(response.status, json.loads(raw) if raw else None)
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            try:
                data = json.loads(raw) if raw else None
            except json.JSONDecodeError:
                data = {"error": raw}
            return HttpResult(exc.code, data)
        except (urllib.error.URLError, TimeoutError, socket.timeout, ConnectionError, OSError) as exc:
            raise TransportUnknown("ACCESS_REVIEW_TRANSPORT_UNKNOWN") from exc

    def health(self) -> HttpResult:
        return self._open(urllib.request.Request(self.base_url + "/health", method="GET"))

    def post(self, path: str, payload: dict[str, Any]) -> HttpResult:
        body = _compact(payload)
        timestamp = str(int(dt.datetime.now(dt.timezone.utc).timestamp() * 1000))
        nonce = secrets.token_urlsafe(18).replace("-", "_")[:24]
        body_hash = _sha256_text(body)
        canonical = "\n".join([self.key_id, timestamp, nonce, "POST", path, body_hash])
        signature = hmac.new(self.secret.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha256).hexdigest()
        request = urllib.request.Request(
            self.base_url + path,
            data=body.encode("utf-8"),
            method="POST",
            headers={
                "content-type": "application/json",
                "x-fare-key-id": self.key_id,
                "x-fare-timestamp": timestamp,
                "x-fare-nonce": nonce,
                "x-fare-signature": signature,
            },
        )
        return self._open(request)


def verify_health(transport: Any, head: str) -> dict[str, Any]:
    try:
        result = transport.health()
    except TransportUnknown as exc:
        raise AccessReviewError("ACCESS_REVIEW_HEALTH_UNAVAILABLE") from exc
    data = result.data if isinstance(result.data, dict) else {}
    if result.status != 200 or data.get("spec") != "1.3" or data.get("mode") not in ALLOWED_MODES or str(data.get("commit_sha", "")).lower() != head.lower():
        raise AccessReviewError("ACCESS_REVIEW_RUNTIME_IDENTITY_MISMATCH")
    return data


def _audit_readback_request(record: dict[str, Any]) -> dict[str, Any]:
    review = record["review"]
    kind = record["kind"]
    return {"evidence_id": review["evidence_id"], "kind": kind, "entity_id": review["source_id" if kind == "source" else "provider_id"]}


def _review_readback_request(record: dict[str, Any]) -> dict[str, Any]:
    review = record["review"]
    kind = record["kind"]
    return {"kind": kind, "entity_id": review["source_id" if kind == "source" else "provider_id"], "review_id": review["review_id"]}


def audit_state(record: dict[str, Any], head: str, response: HttpResult) -> str:
    if response.status != 200 or not isinstance(response.data, dict):
        raise AccessReviewError(f"ACCESS_REVIEW_AUDIT_READBACK_FAILED:{response.status}")
    actual = response.data.get("evidence")
    if actual is None:
        return "absent"
    expected = evidence_for(record, head, created_at=actual.get("created_at") if isinstance(actual, dict) else None)
    keys = ("evidence_id", "gate_id", "spec_version", "commit_sha", "test_report_hash", "provider_readback", "unresolved_items")
    if isinstance(actual, dict) and all(actual.get(k) == expected.get(k) for k in keys):
        return "exact"
    return "mismatch"


def review_state(record: dict[str, Any], reviewer_key_id: str, response: HttpResult) -> str:
    if response.status != 200 or not isinstance(response.data, dict):
        raise AccessReviewError(f"ACCESS_REVIEW_READBACK_FAILED:{response.status}")
    actual = response.data.get("review")
    if actual is None:
        return "absent"
    review = record["review"]
    payload_hash = review_payload_hash(record)
    kind = record["kind"]
    if kind == "source":
        checks = {name: review[name] for name in SOURCE_FIELDS[-6:]}
        expected = {
            "review_id": review["review_id"], "source_id": review["source_id"], "target_state": review["target_state"],
            "access_basis": review["access_basis"], "terms_snapshot_at": review["terms_snapshot_at"], "evidence_id": review["evidence_id"],
            "payload_sha256": payload_hash, "reviewer_key_id": reviewer_key_id, "checks_json": checks,
        }
        registry = response.data.get("registry") or {}
        registry_ok = all([
            registry.get("source_id") == review["source_id"], registry.get("lifecycle_state") == review["target_state"],
            registry.get("status") == review["target_state"], registry.get("access_basis") == review["access_basis"],
            registry.get("terms_snapshot_at") == review["terms_snapshot_at"], int(registry.get("kill_switch", 1)) == 0,
            registry.get("kill_switch_state") == "CLEAR",
        ])
    else:
        checks = {name: review[name] for name in PROVIDER_FIELDS[-3:]}
        expected = {
            "review_id": review["review_id"], "provider_id": review["provider_id"], "access_basis": review["access_basis"],
            "terms_snapshot_at": review["terms_snapshot_at"], "rate_policy": review["rate_policy"], "evidence_id": review["evidence_id"],
            "payload_sha256": payload_hash, "reviewer_key_id": reviewer_key_id, "checks_json": checks,
        }
        registry = response.data.get("registry") or {}
        registry_ok = all([
            registry.get("provider_id") == review["provider_id"], registry.get("access_basis") == review["access_basis"],
            registry.get("terms_snapshot_at") == review["terms_snapshot_at"], registry.get("rate_policy") == review["rate_policy"],
        ])
    if isinstance(actual, dict) and all(actual.get(k) == v for k, v in expected.items()) and registry_ok:
        return "exact"
    return "mismatch"


def _read_state(transport: Any, path: str, payload: dict[str, Any], classifier: Callable[[HttpResult], str]) -> str:
    try:
        return classifier(transport.post(path, payload))
    except TransportUnknown as exc:
        raise AccessReviewError("ACCESS_REVIEW_READBACK_TRANSPORT_UNKNOWN") from exc


def _mutate_once_then_reconcile(
    transport: Any,
    mutation_path: str,
    mutation_payload: dict[str, Any],
    read_path: str,
    read_payload: dict[str, Any],
    classifier: Callable[[HttpResult], str],
) -> str:
    try:
        result = transport.post(mutation_path, mutation_payload)
    except TransportUnknown:
        state = _read_state(transport, read_path, read_payload, classifier)
        if state == "exact":
            return "reconciled"
        if state == "absent":
            raise AccessReviewError("ACCESS_REVIEW_TRANSPORT_UNKNOWN")
        raise AccessReviewError("ACCESS_REVIEW_READBACK_MISMATCH")
    if not (200 <= result.status < 300):
        if result.status == 409:
            state = _read_state(transport, read_path, read_payload, classifier)
            if state == "exact":
                return "reconciled"
        raise AccessReviewError(f"ACCESS_REVIEW_MUTATION_REJECTED:{mutation_path}:{result.status}")
    state = _read_state(transport, read_path, read_payload, classifier)
    if state != "exact":
        raise AccessReviewError("ACCESS_REVIEW_POST_READBACK_MISMATCH")
    return "written"


def process_record(record: dict[str, Any], head: str, reviewer_key_id: str, transport: Any, dry_run: bool = False) -> dict[str, str]:
    review = record["review"]
    audit_payload = evidence_for(record, head)
    audit_read = _audit_readback_request(record)
    audit_classifier = lambda result: audit_state(record, head, result)
    audit_pre = _read_state(transport, "/audit/evidence/readback", audit_read, audit_classifier)
    if audit_pre == "mismatch":
        raise AccessReviewError("ACCESS_REVIEW_AUDIT_PRESTATE_MISMATCH")
    if audit_pre == "absent":
        if dry_run:
            return {"review_id": review["review_id"], "audit": "would_write", "review": "would_write"}
        audit_action = _mutate_once_then_reconcile(transport, "/audit/evidence", audit_payload, "/audit/evidence/readback", audit_read, audit_classifier)
    else:
        audit_action = "existing"

    review_read = _review_readback_request(record)
    review_classifier = lambda result: review_state(record, reviewer_key_id, result)
    review_pre = _read_state(transport, "/access/reviews/readback", review_read, review_classifier)
    if review_pre == "mismatch":
        raise AccessReviewError("ACCESS_REVIEW_PRESTATE_MISMATCH")
    if review_pre == "absent":
        if dry_run:
            review_action = "would_write"
        else:
            endpoint = "/sources/onboarding/review" if record["kind"] == "source" else "/providers/access/review"
            review_action = _mutate_once_then_reconcile(transport, endpoint, review, "/access/reviews/readback", review_read, review_classifier)
    else:
        review_action = "existing"
    return {"review_id": review["review_id"], "audit": audit_action, "review": review_action}


def run(records: list[dict[str, Any]], head: str, reviewer_key_id: str, transport: Any, dry_run: bool = False) -> list[dict[str, str]]:
    verify_health(transport, head)
    if dry_run:
        # Dry-run remains provider-read-only except for signed nonce bookkeeping on exact readbacks.
        pass
    return [process_record(record, head, reviewer_key_id, transport, dry_run=dry_run) for record in records]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Submit immutable human-authored source/provider access reviews")
    parser.add_argument("--input", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    try:
        _require_clean()
        head = _git_head()
        key_id = os.environ.get("FARE_ACCESS_REVIEWER_KEY_ID", "")
        secret = os.environ.get("FARE_ACCESS_REVIEWER_SECRET", "")
        if not key_id:
            raise AccessReviewError("FARE_ACCESS_REVIEWER_KEY_ID_REQUIRED")
        if len(secret) < 16:
            raise AccessReviewError("FARE_ACCESS_REVIEWER_SECRET_REQUIRED")
        records = load_jsonl(pathlib.Path(args.input))
        base_url = resolve_base_url(head, os.environ.get("FARE_RADAR_BASE_URL"))
        transport = SignedHttpTransport(base_url, key_id, secret)
        result = run(records, head, key_id, transport, dry_run=args.dry_run)
        print(json.dumps({"ok": True, "dry_run": args.dry_run, "commit_sha": head, "base_url": base_url, "results": result}, ensure_ascii=False, indent=2))
        return 0
    except (AccessReviewError, OSError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
