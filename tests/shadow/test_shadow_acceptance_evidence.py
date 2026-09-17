from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import production_preflight as preflight
import shadow_review as shadow

COMMIT = "d" * 40
STRATEGIES = ["S09", "S11", "S12", "S14", "S15"]


def canonical_acceptance(**changes):
    data = {
        "pass": True,
        "commit_sha": COMMIT,
        "deployment_mode": "SHADOW_ACCEPTANCE",
        "shadow_days": 14,
        "labeled_candidates": 150,
        "labeled_complex_candidates": 30,
        "labeled_source_discovery_events": 30,
        "labeled_agency_clearance_events": 10,
        "complex_strategy_coverage": STRATEGIES,
        "complex_strategy_missing": [],
        "false_actionable_complex": 0,
        "safety_critical_errors": 0,
        "total_reviews": 220,
    }
    data.update(changes)
    return data


def test_canonical_shadow_acceptance_roundtrip(monkeypatch, tmp_path):
    monkeypatch.setenv("FARE_EVIDENCE_ROOT", str(tmp_path))
    acceptance = canonical_acceptance()
    path = shadow.write_acceptance_evidence(acceptance, COMMIT)
    assert path == tmp_path / "shadow-acceptance.json"
    assert json.loads(path.read_text()) == acceptance
    assert preflight.shadow_ok(COMMIT) is True


def test_shadow_preflight_rejects_alias_or_incomplete_schema(monkeypatch, tmp_path):
    monkeypatch.setenv("FARE_EVIDENCE_ROOT", str(tmp_path))
    path = tmp_path / "shadow-acceptance.json"
    path.write_text(json.dumps({"pass": True, "commit_sha": COMMIT, "days": 14, "labeled": 150, "complex": 30, "safety_errors": 0}))
    assert preflight.shadow_ok(COMMIT) is False


def test_shadow_preflight_rechecks_all_canonical_thresholds(monkeypatch, tmp_path):
    monkeypatch.setenv("FARE_EVIDENCE_ROOT", str(tmp_path))
    for field, value in (
        ("shadow_days", 13),
        ("labeled_candidates", 149),
        ("labeled_complex_candidates", 29),
        ("labeled_source_discovery_events", 29),
        ("labeled_agency_clearance_events", 9),
        ("false_actionable_complex", 1),
        ("safety_critical_errors", 1),
    ):
        (tmp_path / "shadow-acceptance.json").write_text(json.dumps(canonical_acceptance(**{field: value})))
        assert preflight.shadow_ok(COMMIT) is False, field
    (tmp_path / "shadow-acceptance.json").write_text(json.dumps(canonical_acceptance(complex_strategy_missing=["S15"], complex_strategy_coverage=STRATEGIES[:-1])))
    assert preflight.shadow_ok(COMMIT) is False


def test_shadow_review_uses_worker_deploy_provider_evidence(monkeypatch, tmp_path):
    monkeypatch.setenv("FARE_EVIDENCE_ROOT", str(tmp_path))
    provider = tmp_path / "provider"
    provider.mkdir(parents=True)
    origin = "https://fare-radar.example.workers.dev"
    (provider / "worker-deploy.json").write_text(json.dumps({"commit_sha": COMMIT, "worker_origin": origin}))
    monkeypatch.setattr(shadow, "local_head", lambda: COMMIT)
    assert shadow.resolve_base_url(None) == origin
