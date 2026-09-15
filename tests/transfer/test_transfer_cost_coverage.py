import json, pathlib, subprocess
from tests.fixtures import plan

ROOT=pathlib.Path(__file__).resolve().parents[2]

def raw_validate(payload):
    return subprocess.run(['node','dist/cli.js','validate-plan',json.dumps(payload)],cwd=ROOT,text=True,capture_output=True)


def test_cost_complete_requires_transfer_specific_costs():
    p=plan()
    p['transfers'][0]['overnight_transfer']=True
    proc=raw_validate(p)
    assert proc.returncode!=0 and 'OVERNIGHT_HOTEL_COST_REQUIRED' in proc.stderr

    p['costs'].append({
      'cost_id':'hotel','type':'MANDATORY_HOTEL','amount':1200,'currency':'TWD','twd_amount':1200,
      'inclusion_state':'ADD_ON','source_evidence_id':'ev-hotel','dedupe_key':'hotel-b1','certainty':'CONFIRMED',
      'paid_state':'UNPAID','refundable':False,'observed_at':p['costs'][0]['observed_at']
    })
    assert raw_validate(p).returncode==0


def test_cost_complete_requires_airport_change_ground_cost_per_boundary():
    p=plan()
    p['transfers'][0].update({'airport_change':True,'arrival_airport':'ICN','departure_airport':'GMP'})
    proc=raw_validate(p)
    assert proc.returncode!=0 and 'AIRPORT_CHANGE_GROUND_COST_REQUIRED' in proc.stderr

    p['costs'].append({
      'cost_id':'xfer','type':'AIRPORT_CHANGE_GROUND','amount':500,'currency':'TWD','twd_amount':500,
      'inclusion_state':'ADD_ON','source_evidence_id':'ev-ground','dedupe_key':'airport-change-b1','certainty':'CONFIRMED',
      'paid_state':'UNPAID','refundable':False,'observed_at':p['costs'][0]['observed_at']
    })
    assert raw_validate(p).returncode==0


def test_incomplete_candidate_may_exist_without_transfer_costs():
    p=plan(); p['itinerary']['cost_complete']=False
    p['transfers'][0]['overnight_transfer']=True
    assert raw_validate(p).returncode==0
