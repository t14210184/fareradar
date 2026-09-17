from __future__ import annotations

import atexit
import json
import os
import pathlib
import shutil
import subprocess
import tempfile

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
_TEST_EVIDENCE_ROOT = pathlib.Path(tempfile.mkdtemp(prefix="fare-radar-pytest-evidence-"))
os.environ["FARE_EVIDENCE_ROOT"] = str(_TEST_EVIDENCE_ROOT)
atexit.register(shutil.rmtree, _TEST_EVIDENCE_ROOT, ignore_errors=True)


@pytest.fixture(scope="session", autouse=True)
def build_ts():
    if os.environ.get("FARE_SKIP_BUILD") != "1":
        subprocess.run(["tsc", "-p", "tsconfig.json"], cwd=ROOT, check=True)


def cli(cmd: str, payload):
    process = subprocess.run(["node", "dist/cli.js", cmd, json.dumps(payload)], cwd=ROOT, text=True, capture_output=True)
    if process.returncode:
        raise RuntimeError(process.stderr or process.stdout)
    return json.loads(process.stdout)


@pytest.fixture
def run_cli():
    return cli
