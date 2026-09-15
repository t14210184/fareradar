import json, pathlib
ROOT=pathlib.Path(__file__).resolve().parents[2]
def test_provider_contract_fields():
    rows=json.loads((ROOT/'config/providers.seed.json').read_text()); assert rows
    for r in rows:
        for k in ['provider_id','access_basis','terms_snapshot_at','rate_policy','kill_switch_state','owner','connector_state','supported_verification','credential_binding','background_allowed']: assert r.get(k) is not None
        assert r['connector_state'] in {'UNIMPLEMENTED','IMPLEMENTED','PARTNER_REQUIRED'}
        assert isinstance(r['supported_verification'],list)
        # Code may be implemented while commercial/access terms remain deliberately stale.
        # Dispatch is still forbidden until terms + runtime credential readback pass.
        if r['terms_snapshot_at']=='RECHECK_REQUIRED': assert r['kill_switch_state']=='CLEAR'
