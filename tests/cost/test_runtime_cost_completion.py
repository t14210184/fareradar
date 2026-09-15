import json, pathlib, subprocess
ROOT=pathlib.Path(__file__).resolve().parents[2]
def test_direct_all_in_cost_requires_ground_fresh_fx_and_profile_seat_cost():
    p=subprocess.run(['node','tests/node_cost_completion.mjs'],cwd=ROOT,text=True,capture_output=True,check=True); x=json.loads(p.stdout)
    assert x['complete']['cost_complete'] is True and abs(x['complete']['cash_trip_cost_twd']-5464)<0.01
    assert x['stale']['cost_complete'] is False and x['stale']['reason'] in ('CHECKOUT_PRICE_STALE','FX_STALE','BAGGAGE_COST_OR_ALLOWANCE_INCOMPLETE')
    assert x['seatMissing']=={'cost_complete':False,'reason':'SEAT_SELECTION_COST_REQUIRED'}
    assert x['seatComplete']['cost_complete'] is True and x['seatComplete']['cash_trip_cost_twd']==5700
