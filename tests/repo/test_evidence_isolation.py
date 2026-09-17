from __future__ import annotations

import importlib.util
import json
import os
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]


def load_preflight():
    spec = importlib.util.spec_from_file_location("production_preflight_isolation", ROOT / "scripts" / "production_preflight.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_pytest_uses_external_temporary_evidence_root():
    root = pathlib.Path(os.environ["FARE_EVIDENCE_ROOT"]).resolve()
    assert root.is_absolute()
    assert root != (ROOT / "evidence").resolve()
    assert ROOT.resolve() not in root.parents


def test_preflight_provider_reads_only_injected_evidence_root(monkeypatch, tmp_path):
    mod = load_preflight()
    monkeypatch.setenv("FARE_EVIDENCE_ROOT", str(tmp_path))
    provider = tmp_path / "provider"
    provider.mkdir(parents=True)
    expected = {"provider": "github", "marker": "isolated"}
    (provider / "github-readback.json").write_text(json.dumps(expected), encoding="utf-8")
    assert mod.evidence_root() == tmp_path
    assert mod.provider_evidence("github-readback") == expected


def test_relative_evidence_root_fails_closed(monkeypatch):
    mod = load_preflight()
    monkeypatch.setenv("FARE_EVIDENCE_ROOT", "relative/evidence")
    with pytest.raises(ValueError, match="FARE_EVIDENCE_ROOT_MUST_BE_ABSOLUTE"):
        mod.evidence_root()
