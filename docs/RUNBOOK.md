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

Production release remains fail-closed. Local green tests never imply Production readiness.

```bash
npm run preflight
npm run deploy:plan
```

When Cloudflare authentication, required Worker secrets and the D1 account are available, the controller may run:

```bash
npm run deploy:cloudflare
```

The release runner performs, in order: local build, Wrangler dry-run, required-secret readback, remote D1 migrations, deterministic registry seed apply, Worker deploy, deployment-status readback, D1 source-registry count readback, and `/health` exact-commit readback. It writes `.evidence/cloudflare_readback.json` only from provider responses.

After the public GitHub remote exists and CI has completed for the exact HEAD:

```bash
npm run readback:github
```

After a deployed Shadow run has accumulated the required 14-day corpus and labels:

```bash
CLOUDFLARE_WORKER_URL=https://... PIPELINE_TOKEN=... npm run readback:shadow
```

`tools/deploy_preflight.py` accepts these evidence files only when their commit SHA matches the current HEAD; stale evidence cannot promote readiness.
