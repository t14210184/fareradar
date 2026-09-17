# Fare Radar

Cloudflare-first low-fare intelligence radar implementation baseline for spec v1.3.

## Local verification

```bash
npm run check:ts
pytest -q
python scripts/run_gate_evidence.py
```

Local test PASS is not Production PASS. GitHub remote, Cloudflare provider readback, live-provider evidence, and shadow acceptance remain separate gates.
