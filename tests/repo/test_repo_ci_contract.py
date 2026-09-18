from __future__ import annotations

import importlib.util
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
CHECKOUT_SHA = "11d5960a326750d5838078e36cf38b85af677262"
SETUP_NODE_SHA = "49933ea5288caeca8642d1e84afbd3f7d6820020"
SETUP_PYTHON_SHA = "a26af69be951a213d495a4c3e4e4022e16d87065"
UPLOAD_ARTIFACT_SHA = "ea165f8d65b6e75b540449e92b4886f43607fa02"


def load_prepush():
    spec = importlib.util.spec_from_file_location("prepush_acceptance", ROOT / "scripts" / "prepush_acceptance.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_ci_contract_present_and_pins_wrangler_dry_run():
    ci = (ROOT / ".github/workflows/ci.yml").read_text()
    pkg = json.loads((ROOT / "package.json").read_text())
    assert "npm run check:wrangler" in ci
    cmd = pkg["scripts"]["check:wrangler"]
    assert "npm run build" in cmd
    assert "wrangler@4.131.2 deploy --dry-run --config wrangler.ci.jsonc" in cmd


def test_ci_actions_are_immutable_and_minimum_permission():
    ci = (ROOT / ".github/workflows/ci.yml").read_text()
    assert f"actions/checkout@{CHECKOUT_SHA}" in ci
    assert f"actions/setup-node@{SETUP_NODE_SHA}" in ci
    assert f"actions/setup-python@{SETUP_PYTHON_SHA}" in ci
    assert "actions/checkout@v4" not in ci
    assert "actions/setup-node@v4" not in ci
    assert "actions/setup-python@v5" not in ci
    assert "permissions:\n  contents: read\n" in ci
    assert "persist-credentials: false" in ci


def test_ci_wrangler_uses_synthetic_d1_but_production_stays_fail_closed():
    ci = json.loads((ROOT / "wrangler.ci.jsonc").read_text())
    prod = json.loads((ROOT / "wrangler.jsonc").read_text())
    assert ci["triggers"]["crons"] == ["* * * * *"]
    assert prod["triggers"]["crons"] == ["* * * * *"]
    assert prod["secrets"] == ["WORKER_TOKEN", "INGEST_HMAC_SECRETS"]
    assert ci["d1_databases"][0]["database_id"] == "00000000-0000-0000-0000-000000000001"
    assert prod["d1_databases"][0]["database_id"] == "REPLACE_WITH_D1_DATABASE_ID"
    assert ci["d1_databases"][0]["database_id"] != prod["d1_databases"][0]["database_id"]


def test_nested_runtime_evidence_is_gitignored():
    for path in (
        "evidence/provider/github-readback.json",
        "evidence/provider/cloudflare-worker.json",
        "evidence/shadow-acceptance.json",
        "evidence/private/reviews.jsonl",
    ):
        result = subprocess.run(["git", "check-ignore", "-q", path], cwd=ROOT, check=False)
        assert result.returncode == 0, path


def test_prepush_gate_and_hook_contract():
    pkg = json.loads((ROOT / "package.json").read_text())
    assert pkg["scripts"]["check:prepush"] == "python3 scripts/prepush_acceptance.py"
    assert pkg["scripts"]["hooks:install"] == "git config core.hooksPath .githooks"
    hook = ROOT / ".githooks" / "pre-push"
    assert hook.read_text().strip().endswith("python3 scripts/prepush_acceptance.py")
    mode = subprocess.check_output(["git", "ls-files", "-s", ".githooks/pre-push"], cwd=ROOT, text=True)
    assert mode.startswith("100755 ")


def test_prepush_rejects_bare_placeholder_but_allows_d1_sentinel():
    mod = load_prepush()
    token = "PLACE" + "HOLDER"
    assert mod.contains_forbidden_placeholder(f"value = {token}\n") is True
    assert mod.contains_forbidden_placeholder('"database_id":"REPLACE_WITH_D1_DATABASE_ID"') is False
    assert mod.CHECKS == (
        ("npm", "run", "check:ts"),
        ("npm", "run", "check:wrangler"),
        ("pytest", "-q"),
        ("python3", "scripts/validate_invariants.py"),
        ("git", "diff", "--check", "HEAD"),
    )


def test_github_protection_command_is_wired():
    pkg = json.loads((ROOT / "package.json").read_text())
    assert pkg["scripts"]["protect:github"] == "python3 scripts/github_provider.py protect"


def test_worker_preview_urls_are_explicit():
    prod = json.loads((ROOT / "wrangler.jsonc").read_text())
    assert prod["preview_urls"] is True


def test_gate_evidence_is_part_of_required_ci_and_artifact_is_pinned():
    ci = (ROOT / ".github/workflows/ci.yml").read_text()
    pkg = json.loads((ROOT / "package.json").read_text())
    assert pkg["scripts"]["gates:all"] == "python3 scripts/run_gate_evidence.py"
    assert "npm run gates:all" in ci
    assert "FARE_EVIDENCE_ROOT: ${{ runner.temp }}/fare-evidence" in ci
    assert f"actions/upload-artifact@{UPLOAD_ARTIFACT_SHA}" in ci
    assert "actions/upload-artifact@v4" not in ci
    assert "gate-evidence-${{ github.sha }}" in ci
