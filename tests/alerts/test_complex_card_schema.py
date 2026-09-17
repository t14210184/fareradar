def test_complex_alert_explains_cost_and_risk(run_cli):
    x={'itinerary_id':'i','total_cost':9900,'missing':['checked_bag_price'],'protection':'SEPARATE_UNPROTECTED','policy_ttl':'2026-09-16','observed_at':'2026-09-15T00:00:00Z','source_provenance':['obs-1']}
    got=run_cli('complex-alert',x); assert got['kind']=='P0-COMPLEX' and got['total_cost']==9900 and got['missing']
