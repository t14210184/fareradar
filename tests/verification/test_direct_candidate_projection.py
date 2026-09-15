import json, pathlib, subprocess
ROOT=pathlib.Path(__file__).resolve().parents[2]

def test_confirmed_structured_direct_offer_projects_non_actionable_candidate_until_cost_policy_baggage_are_proven():
    p=subprocess.run(['node','tests/node_direct_candidate_projection.mjs'],cwd=ROOT,text=True,capture_output=True,check=True)
    x=json.loads(p.stdout)
    assert x['result']['projection']['projected']==1
    assert x['itin']['strategy_type']=='S00_DIRECT_RT' and x['itin']['verification_state']=='CONFIRMED'
    assert x['itin']['cash_trip_cost_twd'] is None and x['itin']['cost_complete']==0
    assert x['ticket']['ticket_type']=='ROUND_TRIP' and x['ticket']['connection_protection_type']=='NOT_APPLICABLE_DIRECT'
    assert x['ticket']['validating_carrier']=='TT' and len(x['ticket']['segments'])==2
    f={r['facet_type']:r['status'] for r in x['facets']}
    assert f['FARE_VERIFIED']=='PASS' and f['CONNECTION_ACCEPTABLE']=='PASS' and f['COUPON_SEQUENCE_CLEAR']=='PASS'
    assert f['BAGGAGE_FEASIBLE']=='UNKNOWN' and f['DOCUMENT_CLEAR']=='UNKNOWN' and f['POLICY_FRESH']=='UNKNOWN' and f['COST_COMPLETE']=='FAIL'
    assert x['cost']['amount']==4999 and x['cost']['source_offer_id']=='offer-direct' and x['cost']['inclusion_state']=='INCLUDED_IN_OFFER'
    assert x['isActionable'] is False
    assert x['attributionIntent']=={'event_type':'CONFIRMED_CANDIDATE','state':'PENDING'}
