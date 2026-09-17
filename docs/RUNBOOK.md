# Runbook

## Local acceptance

```bash
npm run check:ts
pytest -q
python3 tools/validate_registries.py
node tools/worker_sqlite_smoke.cjs
node tools/ingest_auth_smoke.cjs
```

## Reproducible Gate evidence

Gate evidence must be generated from a clean Git worktree and one immutable commit:

```bash
python3 tools/generate_gate_evidence.py --begin
python3 tools/generate_gate_evidence.py --start 0 --count 8
python3 tools/generate_gate_evidence.py --start 8 --count 8
python3 tools/generate_gate_evidence.py --start 16 --count 8
python3 tools/generate_gate_evidence.py --start 24 --count 8
python3 tools/generate_gate_evidence.py --start 32 --count 5
python3 tools/generate_gate_evidence.py --finalize
```

`LOCAL_TEST_PASS` is not Production PASS. Provider same-source readback, remote CI, Cloudflare deployment evidence, and Shadow acceptance remain separate gates.

## External heavy worker

The worker is optional and never owns canonical state. Configure `FARE_RADAR_WORKER_TOKEN` and `FARE_RADAR_WORKER_ID`; it leases `EXTERNAL_HEAVY` jobs from Cloudflare. The same lease authorizes only the matching source observation. No separate ingest bearer token is required.

## Push-source HMAC

Provision `INGEST_HMAC_SECRETS` as a JSON object mapping each D1 `secret_slot` to its secret. Sender credentials are scoped by `ingest_auth_keys` to source and, for agencies, agency ID. Never put this JSON into Git or D1.

## Production release automation

Production release remains fail-closed. Local green tests never imply Production readiness. Read-only planning remains available through:

```bash
npm run preflight
npm run deploy:plan
npm run readback:github
npm run readback:cloudflare
```

Shared mutations are bounded separately. `npm run deploy:shadow` is Shadow-only and cannot activate Production. `npm run deploy:production` remains blocked until the exact-head Shadow acceptance and all provider/GitHub gates are satisfied and a human has supplied the exact approved commit in `FARE_PRODUCTION_HUMAN_APPROVED_HEAD`.

## GitHub and Cloudflare provider readback

GitHub evidence is valid only for the exact public repository, default `main`, exact commit, successful exact-head CI, and branch protection requiring the `test` status. A remote URL alone is never a provider PASS.

Cloudflare readback is one same-source session across account identity, D1, Worker settings, active deployment, secrets, schedules, migrations, baseline seeds, and dispatchable source/provider human-review evidence. The Worker must expose exactly one `* * * * *` cron, one active version at 100%, the exact `FARE_COMMIT_SHA` and deployment mode, the exact D1 binding, no legacy ingest secret/flag, and an enabled workers.dev origin. Evidence from different readback sessions cannot be spliced into a Production PASS.

## Live credential probes

`npm run probe:live` verifies the deployed runtime identity before checking credentials. The Worker token probe uses a synthetic nonexistent verification lease: a valid token must pass authentication and stop at `LIVE_SOURCE_LEASE_REQUIRED`, so no business mutation occurs. Shadow and Access reviewer probes use their existing signed readback routes; they consume replay-protection nonces but do not create or modify review records. All three supplied credential values must be proven active against the exact deployed commit.

## Bounded Shadow deployment

`npm run deploy:shadow` requires a clean worktree, exact `FARE_SHADOW_EXPECTED_HEAD`, current exact-head local Gate evidence, a non-placeholder D1 binding, and all required Cloudflare/reviewer credentials. It runs `npm run build` before any provider access, reads the existing Worker prestate, and dispatches exactly one pinned `wrangler@4.131.2 deploy` with `--keep-vars --strict`, `FARE_COMMIT_SHA=<HEAD>`, and hard-coded `FARE_DEPLOYMENT_MODE=SHADOW_ACCEPTANCE`.

A failed or timed-out Wrangler process is never blindly resent. The driver performs strict Cloudflare same-source readback. Exact expected state is accepted as confirmed; provider state identical to the prestate is classified `SHADOW_DEPLOY_NOT_APPLIED`; any changed but non-matching state is `SHADOW_DEPLOY_PARTIAL_OR_AMBIGUOUS` and stops. A confirmed deployment must then pass all live credential probes before evidence is written.

## Human-gated Production activation

`npm run deploy:production` cannot create its own approval. `FARE_PRODUCTION_HUMAN_APPROVED_HEAD` must already exist, must be a 40-hex commit, and must equal the clean local HEAD. `npm run preflight` must report exactly one blocker: `PRODUCTION_ACTIVATION_REQUIRED`. This means local Gate evidence, GitHub exact-head CI/protection, Cloudflare same-session readback, secrets, D1/migrations/seeds/reviewer evidence, and exact-head 14-day Shadow acceptance are already satisfied.

Immediately before the Production mutation, the driver reads the live Worker prestate and requires the same commit still deployed in `SHADOW_ACCEPTANCE`. It then performs exactly one pinned Wrangler deploy with `--keep-vars --strict` and hard-coded `FARE_DEPLOYMENT_MODE=PRODUCTION`. A lost/failed deploy response is handled exactly like Shadow: strict same-source readback first, no blind resend; unchanged provider state means `PRODUCTION_DEPLOY_NOT_APPLIED`, and any changed non-matching state means `PRODUCTION_DEPLOY_PARTIAL_OR_AMBIGUOUS`. Exact Production state must pass live credential probes before provider evidence is replaced.

`production_ready=true` is impossible while the exact deployed Worker remains in Shadow mode; preflight keeps `PRODUCTION_ACTIVATION_REQUIRED` until the exact-head Production readback exists.

## Live provider offer expiry lifecycle

The five-minute cron actively checks the exact LIVE offers supporting current `CONFIRMED` verification results. Expected behavior when a support expires:

1. Re-evaluate already-linked fresh evidence first.
2. Preserve `CONFIRMED` with rotated support when redundant evidence is sufficient.
3. Otherwise downgrade to `PROBABLE`, mark `FARE_VERIFIED=STALE`, cancel/suppress unsent DEAL notifications, and enqueue a deterministic `DEAL-UPDATE` for a previously visible DEAL.
4. Re-use the existing provider search plan to enqueue a bounded `BACKGROUND` reprice keyed by the lifecycle event.
5. Provider completion recomputes verification and projects fresh cost/readiness lineage.

Local regression coverage:

```bash
pytest -q tests/verification/test_multi_provider.py
pytest -q tests/capacity/test_five_min_cron_budget.py
node tests/node_live_offer_expiry.mjs
node tests/node_live_offer_expiry_redundant.mjs
```

The capacity fixtures require the normal five-minute path to stay at or below the internal 40-query target; lifecycle work preempts optional work for that tick.

## Shadow review transport and retry safety

Human-authored Shadow labels stay outside the public repository. Validate or submit an exact JSONL file with `npm run shadow:review -- --input /private/shadow-reviews.jsonl [--dry-run]` and private `FARE_HMAC_KEY_ID` / `FARE_HMAC_SECRET` credentials. The client requires a clean exact HEAD and verifies `/health` is `spec=1.3`, `SHADOW_ACCEPTANCE`, and the same commit before any review operation. Duplicate `sample_id` values and duplicate canonical review units are rejected locally.

Every review mutation is readback-first through `/shadow/reviews/readback`. An already-present exact row is confirmed and never resent; an absent row permits one bounded write; a mismatched row fails closed. After a successful write the exact row is read back again. A transport timeout is reconciled immediately with the same readback endpoint: exact state is accepted as confirmed, absent state is reported as unknown/not-applied without an in-process resend, and mismatched state is ambiguous and blocks progress. Rerun only the identical JSONL so the next attempt begins with the same pre-readback fence. The client finishes by reading `/shadow/acceptance/readback`; it never synthesizes labels or safety judgments to satisfy thresholds.

## Human access review transport

Source/provider access decisions remain human-authored evidence and the JSONL stays outside the repository. Run `npm run access:review -- --input /private/access-reviews.jsonl --dry-run` before submitting the identical file without `--dry-run`. The launcher requires a clean exact HEAD, an exact-head Worker origin, and `/health` reporting spec `1.3`, deployment mode `SHADOW_ACCEPTANCE` or `PRODUCTION`, and the exact local commit. It accepts the current `deployment_mode` health field and the historical `mode` alias only for compatibility.

Before every audit-evidence or access-review mutation, the client performs same-source readback. Exact immutable state is not resent; absent state permits one bounded mutation; mismatched state fails closed. A lost mutation response is reconciled by readback before any retry. Provider access bases remain limited to `OFFICIAL_API`, `PARTNER_CONTRACT`, `AIRLINE_DIRECT`, `MANUAL_ORACLE`, or `PUBLIC_PAGE_MONITOR`; automation never invents or approves access, terms, privacy, or enablement decisions.
