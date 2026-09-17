from tests.fixtures import plan
def test_included_not_readded_and_duplicate_dedup(run_cli):
    p=plan(); p['costs'].append(dict(p['costs'][1])); got=run_cli('cash',{'offer_total_twd':5000,'components':p['costs']}); assert got=={'cash_trip_cost_twd':5900,'cost_complete':True}
