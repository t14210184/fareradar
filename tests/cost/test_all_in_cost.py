from tests.fixtures import plan
def test_unknown_cost_never_complete(run_cli):
    p=plan(); p['costs'][1]['inclusion_state']='UNKNOWN'; got=run_cli('cash',{'offer_total_twd':5000,'components':p['costs']}); assert got['cost_complete'] is False
