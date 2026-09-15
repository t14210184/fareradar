import json, pathlib, subprocess
ROOT=pathlib.Path(__file__).resolve().parents[2]

def test_promotion_flight_number_constraint_filters_live_provider_offers():
    p=subprocess.run(['node','tests/node_promo_flight_constraint.mjs'],cwd=ROOT,text=True,capture_output=True,check=True)
    x=json.loads(p.stdout)
    assert x['mismatch']=={
        'verification_state':'PROBABLE','reason':'PROMOTION_CONSTRAINT_MISMATCH',
        'best_offer_id':None,'best_offer_total':None,'live_offer_count':0,'provider_count':0,
    }
    assert x['queueAfterMismatch']=='PENDING'
    assert x['eligible']['verification_state']=='PROBABLE'
    assert x['eligible']['reason']=='SINGLE_LIVE_SOURCE'
    assert x['eligible']['best_offer_id']=='offer-right'
    assert x['eligible']['best_offer_total']==4200
    assert x['eligible']['live_offer_count']==1 and x['eligible']['provider_count']==1
    assert x['queueAfterEligible']=='PENDING'

    assert x['currencyMismatch']=={'verification_state':'PROBABLE','reason':'PROMOTION_CONSTRAINT_MISMATCH','best_offer_id':None,'live_offer_count':0}
    assert x['couponUnverified']=={'verification_state':'PROBABLE','reason':'PROMOTION_CONSTRAINT_UNVERIFIED','best_offer_id':None,'live_offer_count':0}
