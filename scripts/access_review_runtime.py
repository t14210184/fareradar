from __future__ import annotations

import access_review as client


def verify_health_compat(transport, head: str):
    try:
        result = transport.health()
    except client.TransportUnknown as exc:
        raise client.AccessReviewError("ACCESS_REVIEW_HEALTH_UNAVAILABLE") from exc
    data = result.data if isinstance(result.data, dict) else {}
    mode = data.get("deployment_mode", data.get("mode"))
    if result.status != 200 or data.get("spec") != "1.3" or mode not in client.ALLOWED_MODES or str(data.get("commit_sha", "")).lower() != head.lower():
        raise client.AccessReviewError("ACCESS_REVIEW_RUNTIME_IDENTITY_MISMATCH")
    return data


client.verify_health = verify_health_compat

if __name__ == "__main__":
    raise SystemExit(client.main())
