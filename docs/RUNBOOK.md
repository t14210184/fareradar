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
