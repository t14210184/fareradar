import json, pathlib
ROOT=pathlib.Path(__file__).resolve().parents[2]
def test_source_contract_fields_and_unique_ids():
    rows=json.loads((ROOT/'config/sources.seed.json').read_text()); ids=[r['source_id'] for r in rows]; assert len(ids)==len(set(ids))
    required=['market','language','access_basis','fetch_method','terms_snapshot_at','retention_policy','kill_switch','owner']
    for r in rows:
        for k in required: assert r.get(k) is not None
