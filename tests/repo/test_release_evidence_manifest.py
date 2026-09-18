from __future__ import annotations

import importlib.util
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("release_manifest", ROOT / "scripts/release_evidence_manifest.py")
release_manifest = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(release_manifest)


def final_doc() -> dict:
    return {
        "commit_sha": "a" * 40,
        "spec_sha256": "b" * 64,
        "dependency_lock_sha256": "c" * 64,
        "test_corpus_sha256": "d" * 64,
        "summary": {"LOCAL_TEST_PASS": 37, "LOCAL_TEST_FAIL": 0, "EVIDENCE_INCOMPLETE": 0},
        "full_suite": {"status": "FULL_SUITE_PASS", "report_sha256": "e" * 64},
    }


def test_release_manifest_binds_exact_head_hashes_ci_and_artifact_identity():
    manifest = release_manifest.build_manifest(
        final_doc(),
        run_id="12345",
        artifact_id="67890",
        artifact_digest="sha256:" + "f" * 64,
        artifact_url="https://github.com/example/repo/actions/runs/12345/artifacts/67890",
    )
    assert manifest["schema_version"] == 1
    assert manifest["commit_sha"] == "a" * 40
    assert manifest["spec_hash"] == "b" * 64
    assert manifest["dependency_lock_hash"] == "c" * 64
    assert manifest["test_corpus_hash"] == "d" * 64
    assert manifest["gate_summary"]["LOCAL_TEST_PASS"] == 37
    assert manifest["ci_run_id"] == "12345"
    assert manifest["gate_artifact"]["id"] == "67890"
    assert manifest["gate_artifact"]["digest"].startswith("sha256:")


def test_release_manifest_fails_closed_on_incomplete_gate_evidence():
    doc = final_doc()
    doc["summary"]["LOCAL_TEST_PASS"] = 36
    with pytest.raises(RuntimeError, match="GATE_EVIDENCE_NOT_COMPLETE"):
        release_manifest.build_manifest(
            doc,
            run_id="1",
            artifact_id="2",
            artifact_digest="sha256:x",
            artifact_url="https://example.invalid/artifact",
        )
