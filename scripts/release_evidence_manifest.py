from __future__ import annotations

import json
import os
import pathlib
import sys


def require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"{name}_REQUIRED")
    return value


def build_manifest(final: dict, *, run_id: str, artifact_id: str, artifact_digest: str, artifact_url: str) -> dict:
    if final.get("summary") != {
        "LOCAL_TEST_PASS": 37,
        "LOCAL_TEST_FAIL": 0,
        "EVIDENCE_INCOMPLETE": 0,
    }:
        raise RuntimeError("GATE_EVIDENCE_NOT_COMPLETE")
    if (final.get("full_suite") or {}).get("status") != "FULL_SUITE_PASS":
        raise RuntimeError("FULL_SUITE_NOT_PASS")
    return {
        "schema_version": 1,
        "kind": "fare-radar-release-evidence-manifest",
        "commit_sha": final["commit_sha"],
        "spec_hash": final["spec_sha256"],
        "dependency_lock_hash": final["dependency_lock_sha256"],
        "test_corpus_hash": final["test_corpus_sha256"],
        "gate_summary": final["summary"],
        "full_suite": final["full_suite"],
        "ci_run_id": run_id,
        "gate_artifact": {
            "name": f"gate-evidence-{final['commit_sha']}",
            "id": artifact_id,
            "digest": artifact_digest,
            "url": artifact_url,
        },
    }


def main() -> int:
    try:
        evidence_root = pathlib.Path(require_env("FARE_EVIDENCE_ROOT")).expanduser()
        manifest_root = pathlib.Path(require_env("FARE_MANIFEST_ROOT")).expanduser()
        if not evidence_root.is_absolute() or not manifest_root.is_absolute():
            raise RuntimeError("EVIDENCE_AND_MANIFEST_ROOTS_MUST_BE_ABSOLUTE")
        final = json.loads((evidence_root / "gate-evidence-latest.json").read_text())
        manifest = build_manifest(
            final,
            run_id=require_env("GITHUB_RUN_ID"),
            artifact_id=require_env("GATE_ARTIFACT_ID"),
            artifact_digest=require_env("GATE_ARTIFACT_DIGEST"),
            artifact_url=require_env("GATE_ARTIFACT_URL"),
        )
        manifest_root.mkdir(parents=True, exist_ok=True)
        out = manifest_root / "release-evidence-manifest.json"
        out.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, sort_keys=True), file=sys.stderr)
        return 2
    print(json.dumps({"ok": True, "manifest": str(out), "commit_sha": manifest["commit_sha"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
