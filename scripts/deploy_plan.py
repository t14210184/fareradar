from __future__ import annotations

import json

from production_preflight import evaluate

ORDERED_SHARED_STEPS = [
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


def plan():
    state = evaluate()
    return {
        "mutation_allowed": False,
        "reason": "READ_ONLY_DEPLOY_PLAN_REQUIRES_PROVIDER_MUTATION_PERMIT",
        "code_ready": state["code_ready"],
        "production_ready": state["production_ready"],
        "commit_sha": state["commit_sha"],
        "blockers": state["blockers"],
        "blocker_details": state["blocker_details"],
        "ordered_shared_steps": ORDERED_SHARED_STEPS,
    }


if __name__ == "__main__":
    print(json.dumps(plan(), ensure_ascii=False, indent=2))
