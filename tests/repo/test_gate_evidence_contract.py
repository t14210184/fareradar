from __future__ import annotations

import importlib.util
import os
import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("ge", ROOT / "scripts/gate_evidence.py")
ge = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(ge)


def test_spec_is_single_source_for_all_37_gate_commands_and_thresholds():
    rows = ge.parse_gate_mapping()
    assert [row["gate_id"] for row in rows] == [f"PG{i:02d}" for i in range(37)]
    assert all(row["exact_command"].startswith("pytest -q tests/") for row in rows)
    assert all(row["expected_threshold"] for row in rows)


def test_evidence_context_binds_head_spec_dependencies_and_test_corpus():
    ctx = ge.context()
    assert len(ctx["commit_sha"]) == 40
    assert all(len(ctx[key]) == 64 for key in ["spec_sha256", "dependency_lock_sha256", "test_corpus_sha256"])


def test_gate_evidence_root_can_be_external_and_must_be_absolute(tmp_path):
    target = tmp_path / "gate-evidence"
    env = os.environ.copy()
    env["FARE_EVIDENCE_ROOT"] = str(target)
    result = subprocess.run(
        ["python3", "scripts/gate_evidence.py", "--show-context"],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert target.is_dir()

    env["FARE_EVIDENCE_ROOT"] = "relative/evidence"
    result = subprocess.run(
        ["python3", "scripts/gate_evidence.py", "--show-context"],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode != 0
    assert "FARE_EVIDENCE_ROOT_MUST_BE_ABSOLUTE" in result.stderr
