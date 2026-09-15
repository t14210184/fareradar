from __future__ import annotations
import json, pathlib, subprocess, pytest
ROOT = pathlib.Path(__file__).resolve().parents[1]

@pytest.fixture(scope="session", autouse=True)
def build_ts():
    subprocess.run(["tsc","-p","tsconfig.json"], cwd=ROOT, check=True)

def cli(cmd: str, payload):
    p=subprocess.run(["node","dist/cli.js",cmd,json.dumps(payload)],cwd=ROOT,text=True,capture_output=True)
    if p.returncode:
        raise RuntimeError(p.stderr or p.stdout)
    return json.loads(p.stdout)

@pytest.fixture
def run_cli(): return cli
