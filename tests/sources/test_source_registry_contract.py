import json, pathlib
ROOT=pathlib.Path(__file__).resolve().parents[2]
def test_source_contract_fields_and_unique_ids():
    rows=json.loads((ROOT/'config/sources.seed.json').read_text()); ids=[r['source_id'] for r in rows]; assert len(ids)==len(set(ids))
    required=['owner_type','source_class','canonical_domain_or_account','market','language','currency','route_scope','access_basis','fetch_method','push_capable','discovery_trust','verification_authority','lead_score','yield_score','fare_freshness','requires_repricing','parser','terms_snapshot_at','privacy_class','retention_policy','min_interval_ms','max_burst','backoff_policy','kill_switch_state','status']
    for r in rows:
        for k in required: assert k in r and r[k] is not None
