# Fare Verification

Discovery claims, cached indicative fares, newsletters, and social posts do not become confirmed fares without seller/provider readback. Amadeus Self-Service is excluded as the sole verifier for LCC itineraries.

## Live-offer support lineage

A `CONFIRMED` candidate records the exact live `offer_snapshots` that justified the verdict in `candidate_verification_supports`. The verification result is therefore not allowed to outlive the supporting offer evidence silently.

When a supporting LIVE offer reaches `expires_at`, the five-minute lifecycle pass actively re-evaluates all already-linked fresh evidence:

- if redundant fresh evidence still satisfies the verification rule, support lineage rotates to that evidence and confirmation is preserved without user-visible churn;
- otherwise the result becomes `PROBABLE`, `FARE_VERIFIED` becomes `STALE`, unsent DEAL notifications are cancelled/suppressed, and any already delivered/in-flight DEAL gets a deterministic `DEAL-UPDATE` correction intent;
- the same lifecycle event queues a bounded background reprice from the existing provider search plan. The lifecycle event is the refresh idempotency key, so crash/replay does not create a second provider job;
- when a fresh provider offer returns, verification is recomputed, the direct candidate may become `CONFIRMED` again, and cost/readiness lineage moves to the new offer.

`live_offer_lifecycle_events` is an audit/recovery record, not a replacement workflow engine. External provider execution still uses the existing `verification_jobs` and `provider_job_consumers` path.
