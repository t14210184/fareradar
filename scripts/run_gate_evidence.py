from __future__ import annotations

import json
import pathlib
import sys

import gate_evidence as gate


GENERATED_PATTERNS = (
    "gate-stage-*.json",
    "full-suite-stage-*.json",
    "gate-evidence-latest.json",
)


def clean_generated(out: pathlib.Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    for pattern in GENERATED_PATTERNS:
        for path in out.glob(pattern):
            if path.is_file():
                path.unlink()


def run_all() -> dict:
    clean_generated(gate.OUT)
    mapping = gate.parse_gate_mapping()
    gate_stage_count = (len(mapping) + gate.GATE_STAGE_SIZE - 1) // gate.GATE_STAGE_SIZE

    for index in range(gate_stage_count):
        doc = gate.gate_stage(index)
        failed = [row["gate_id"] for row in doc["gates"] if row.get("status") != "LOCAL_TEST_PASS"]
        if failed:
            raise RuntimeError("GATE_STAGE_FAILED:" + ",".join(failed))

    for index in range(gate.SUITE_STAGE_COUNT):
        doc = gate.suite_stage(index)
        if doc.get("status") != "FULL_SUITE_STAGE_PASS":
            raise RuntimeError(f"FULL_SUITE_STAGE_FAILED:{index}")

    final = gate.finalize()
    if final.get("summary") != {
        "LOCAL_TEST_PASS": 37,
        "LOCAL_TEST_FAIL": 0,
        "EVIDENCE_INCOMPLETE": 0,
    }:
        raise RuntimeError("GATE_FINAL_SUMMARY_MISMATCH")
    if (final.get("full_suite") or {}).get("status") != "FULL_SUITE_PASS":
        raise RuntimeError("GATE_FULL_SUITE_NOT_PASS")
    return final


def main() -> int:
    try:
        final = run_all()
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc), "evidence_root": str(gate.OUT)}, sort_keys=True))
        return 2
    print(json.dumps({
        "ok": True,
        "commit_sha": final["commit_sha"],
        "summary": final["summary"],
        "full_suite": final["full_suite"],
        "evidence_root": str(gate.OUT),
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
