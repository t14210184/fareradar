# Architecture

Cloudflare Worker + D1 is the canonical control/data plane. Heavy browser verification is an optional outbound Win11 worker. Source acquisition is push-first: webhook/email/RSS/API/conditional HTTP before browser/OCR. The worker cron acts as a bounded dispatcher only.

The five-minute critical lifecycle lane runs before optional search/provisional work. Agency inventory expiry and live-provider-offer expiry each process at most one bounded item per tick. If either lifecycle performs work, that tick returns before optional planner/provisional/burst work. This keeps expiry correction and durable outbox safety ahead of discovery throughput while preserving the internal D1 query margin.

Live provider verification is evidence-linked rather than timer-only: `candidate_verification_results` records its supporting offers through `candidate_verification_supports`, and `live_offer_lifecycle_events` captures expiry handling. Existing fresh evidence is re-evaluated before any user-visible downgrade; only a confirmation that actually loses sufficient support triggers correction plus targeted background repricing.
