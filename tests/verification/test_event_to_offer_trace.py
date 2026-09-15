def test_claims_without_live_or_seller_readback_never_confirm(run_cli):
    ev=[{'kind':'PROMOTION','authority':'HIGH_FOR_OWN_TERMS'},{'kind':'SOCIAL','authority':'LOW'},{'kind':'CACHED_FARE','authority':'INDICATIVE'}]
    assert run_cli('can-confirm',ev) is False
    assert run_cli('can-confirm',ev+[{'kind':'LIVE_OFFER','authority':'BOOKABLE'}]) is True

def test_promotion_live_offer_must_satisfy_eligible_flight_numbers():
    import json, pathlib, subprocess
    root=pathlib.Path(__file__).resolve().parents[2]
    p=subprocess.run(['node','tests/node_promo_flight_constraint.mjs'],cwd=root,text=True,capture_output=True,check=True)
    x=json.loads(p.stdout)
    assert x['mismatch']['reason']=='PROMOTION_CONSTRAINT_MISMATCH'
    assert x['mismatch']['live_offer_count']==0 and x['mismatch']['provider_count']==0
    assert x['queueAfterMismatch']=='PENDING'
    assert x['eligible']['reason']=='SINGLE_LIVE_SOURCE'
    assert x['eligible']['best_offer_id']=='offer-right'
