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

Production release remains fail-closed. Local green tests never imply Production readiness. The repository currently exposes only read-only release planning commands:

```bash
npm run preflight
npm run deploy:plan
```

`deploy:plan` never mutates GitHub or Cloudflare. It prints the exact external blockers and ordered shared-mutation steps. GitHub remote creation, Cloudflare authentication, D1 creation/binding, secret provisioning, Worker deployment and provider readback require an authorized provider connector or equivalent mutation channel plus same-source readback; there is intentionally no deployment mutation command in `package.json`.

After deployment exists, Shadow acceptance remains separate. Production readiness is only allowed after the 14-day labeled Shadow corpus passes the v1.3 acceptance evaluator and `npm run preflight` returns no blockers.

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
