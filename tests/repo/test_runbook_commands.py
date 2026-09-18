from __future__ import annotations

import json
import pathlib
import re
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[2]


def test_documented_release_commands_exist_and_plan_is_read_only():
    pkg = json.loads((ROOT / "package.json").read_text())
    runbook = (ROOT / "docs/RUNBOOK.md").read_text()

    documented = set(re.findall(r"npm run ([A-Za-z0-9:_-]+)", runbook))
    assert documented
    assert documented <= set(pkg["scripts"])

    required = {
        "check:prepush",
        "gates:all",
        "preflight",
        "deploy:plan",
        "protect:github",
        "provision:shadow",
        "deploy:shadow",
        "readback:cloudflare",
        "probe:live",
        "access:review",
        "shadow:review",
        "deploy:production",
    }
    assert required <= documented
    assert "tools/" not in runbook
    assert "VERSIONED_SHADOW_UPDATE" not in runbook
    assert "preview-first" in runbook
    assert "Worker Version only" in runbook

    process = subprocess.run(
        ["python3", "scripts/deploy_plan.py"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    got = json.loads(process.stdout)
    assert got["mutation_allowed"] is False
    assert got["reason"] == "READ_ONLY_DEPLOY_PLAN_REQUIRES_PROVIDER_MUTATION_PERMIT"
    assert len(got["commit_sha"]) == 40
    assert got["ordered_shared_steps"] == [
        "VERIFY_EXACT_HEAD_GATE_EVIDENCE_AND_GITHUB_CI",
        "ENABLE_GITHUB_MAIN_PROTECTION_AND_SAME_SOURCE_READBACK",
        "CREATE_OR_REUSE_D1_AND_APPLY_MIGRATIONS_SEEDS",
        "BIND_REAL_D1_IN_RELEASE_COMMIT_AND_VERIFY_RELEASE_CI",
        "BOOTSTRAP_OR_VERSION_UPDATE_SHADOW_WORKER_AND_RUN_LIVE_PROBES",
        "COMPLETE_HUMAN_SOURCE_AND_PROVIDER_ACCESS_REVIEWS",
        "RUN_FULL_CLOUDFLARE_SAME_SESSION_READBACK",
        "ACCUMULATE_AND_VERIFY_14_DAY_SHADOW_ACCEPTANCE",
        "RE_RUN_PRODUCTION_PREFLIGHT",
        "OBTAIN_EXACT_HEAD_HUMAN_PRODUCTION_APPROVAL",
        "UPLOAD_ZERO_TRAFFIC_PRODUCTION_VERSION_AND_PREVIEW_PROBE",
        "ACTIVATE_EXACT_VERSION_100_PERCENT_AND_POST_READBACK_OR_ROLLBACK",
    ]
