from __future__ import annotations

import argparse
import json
import os

import cloudflare_provider as cf
import d1_recovery as recovery


class D1RestoreError(RuntimeError):
    pass


def restore(api, *, database_id: str, bookmark: str, approved_bookmark: str, execute: bool) -> dict:
    db = cf._result(api.get(f"/d1/database/{database_id}"), "D1_RESTORE_DATABASE_READBACK_FAILED")
    actual_id = str((db or {}).get("uuid", (db or {}).get("id", ""))) if isinstance(db, dict) else ""
    if actual_id != database_id:
        raise D1RestoreError("D1_RESTORE_DATABASE_IDENTITY_MISMATCH")
    current = recovery.current_bookmark(api, database_id)
    plan = {
        "database_id": database_id,
        "current_bookmark": current,
        "restore_bookmark": bookmark,
        "destructive": True,
        "human_gate_required": True,
    }
    if not execute:
        return {"ok": True, "mode": "PLAN_ONLY", **plan}
    if not approved_bookmark or approved_bookmark != bookmark:
        raise D1RestoreError("D1_RESTORE_HUMAN_APPROVAL_REQUIRED")
    result = cf._result(
        api.post(f"/d1/database/{database_id}/time_travel/restore", {"bookmark": bookmark}),
        "D1_RESTORE_FAILED_OR_UNKNOWN",
    )
    post = recovery.current_bookmark(api, database_id)
    return {"ok": True, "mode": "RESTORED", **plan, "provider_result": result, "post_restore_bookmark": post}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bookmark", required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    account_id = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "")
    token = os.environ.get("CLOUDFLARE_API_TOKEN", "")
    database_id = os.environ.get("FARE_D1_DATABASE_ID", "")
    approved = os.environ.get("FARE_D1_RESTORE_HUMAN_APPROVED_BOOKMARK", "")
    if not account_id or not token or not database_id:
        print(json.dumps({"ok": False, "error": "D1_RESTORE_ENV_INCOMPLETE"}, sort_keys=True))
        return 2
    try:
        result = restore(cf.CloudflareApi(account_id, token), database_id=database_id, bookmark=args.bookmark, approved_bookmark=approved, execute=args.execute)
    except (D1RestoreError, recovery.D1RecoveryError, cf.CloudflareProviderError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
