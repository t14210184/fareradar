import json, pathlib
ROOT=pathlib.Path(__file__).resolve().parents[2]
def test_provider_contract_fields():
    rows=json.loads((ROOT/'config/providers.seed.json').read_text()); assert rows
    for r in rows:
        for k in ['provider_id','access_basis','terms_snapshot_at','rate_policy','kill_switch_state','owner']: assert r.get(k) is not None
