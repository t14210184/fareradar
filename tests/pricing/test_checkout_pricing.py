import json, pathlib, subprocess
ROOT=pathlib.Path(__file__).resolve().parents[2]
def test_checkout_pricing_is_user_request_and_secret_free():
    p=subprocess.run(['node','tests/node_checkout_pricing.mjs'],cwd=ROOT,text=True,capture_output=True,check=True); x=json.loads(p.stdout)
    assert x['jobs'][0]['job_type']=='CHECKOUT_REPRICE' and x['jobs'][0]['provider_mode']=='USER_REQUEST'
    assert x['payload']['credential_binding']=='DUFFEL_PAYMENT_CARD_ID' and x['leaksCard'] is False
    assert x['stored']['grand_total']==6000 and x['stored']['surcharge_total']==100
    assert x['stored']['price_scope']=='CHECKOUT_TOTAL_WITH_SELECTED_SERVICES_AND_PAYMENT_SURCHARGE'
    assert x['badService']=='SELECTED_SERVICE_NOT_AVAILABLE'

def test_checkout_quote_projects_flight_cost_but_does_not_claim_trip_cost_complete():
    p=subprocess.run(['node','tests/node_checkout_projection.mjs'],cwd=ROOT,text=True,capture_output=True,check=True); x=json.loads(p.stdout)
    assert x['projected']['done']>=1 and x['event']['state']=='DONE'
    assert x['cost']['type']=='CHECKOUT_TOTAL' and x['cost']['amount']==5100 and x['cost']['pricing_quote_id']=='qp'
    assert x['facet']['status']=='FAIL' and x['facet']['reason_code']=='FLIGHT_CHECKOUT_PRICED_OTHER_COSTS_PENDING'
