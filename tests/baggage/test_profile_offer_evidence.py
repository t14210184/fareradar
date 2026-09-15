import json, pathlib, subprocess
ROOT=pathlib.Path(__file__).resolve().parents[2]
def js(expr):
    code=f"import {{evaluateBaggageEvidence}} from './dist/baggage.js'; console.log(JSON.stringify({expr}))"
    p=subprocess.run(['node','--input-type=module','-e',code],cwd=ROOT,text=True,capture_output=True,check=True); return json.loads(p.stdout)
def test_no_checked_bag_profile_is_feasible_without_ancillary_lookup():
    x=js("evaluateBaggageEvidence({slices:[{segments:[{}]}]},{checked_bags_by_slice:[0],checked_bag_kg:0})")
    assert x['status']=='PASS' and x['reason']=='NO_CHECKED_BAG_REQUIRED'
def test_included_checked_bag_must_cover_each_segment_passenger():
    structure={"slices":[{"segments":[{"passengers":[{"passenger_id":"p1","baggages":[{"type":"checked","quantity":1}]}]}]},{"segments":[{"passengers":[{"passenger_id":"p1","baggages":[{"type":"checked","quantity":1}]}]}]}],"available_services":[]}
    x=js(f"evaluateBaggageEvidence({json.dumps(structure)},{json.dumps({'checked_bags_by_slice':[0,1],'checked_bag_kg':20})})")
    assert x['status']=='PASS' and x['reason']=='REQUIRED_CHECKED_BAG_INCLUDED'
def test_available_baggage_service_does_not_claim_profile_fit_until_priced_and_matched():
    structure={"slices":[{"segments":[{"passengers":[{"passenger_id":"p1","baggages":[]}]}]}],"available_services":[{"type":"baggage","total_amount":"900.00"}]}
    x=js(f"evaluateBaggageEvidence({json.dumps(structure)},{json.dumps({'checked_bags_by_slice':[1],'checked_bag_kg':20})})")
    assert x['status']=='UNKNOWN' and x['reason']=='BAGGAGE_ADDON_AVAILABLE_NEEDS_PRICING'
