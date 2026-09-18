# Fare Radar

Cloudflare-first low-fare intelligence radar implementation baseline for spec v1.3.

## Local verification

```bash
npm ci --ignore-scripts
npm run hooks:install
npm run check:prepush
npm run gates:all
```

The GitHub `test` workflow also runs the exact-head 37-PG Gate evidence pipeline and retains the generated evidence as a commit-bound artifact.

Local or CI PASS is not Production PASS. Production readiness additionally requires GitHub main protection/provider readback, the real D1 release binding, Cloudflare same-session readback, live credential probes, human source/provider access reviews, exact-head 14-day Shadow acceptance, and explicit exact-head human Production approval.

See `docs/RUNBOOK.md` for the bounded provisioning, Shadow deployment, and preview-first Production release sequence.
