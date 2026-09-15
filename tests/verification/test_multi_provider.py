def test_independent_live_sources_must_match(run_cli):
    ev=[{'provider':'p1','kind':'LIVE_OFFER','price':10000,'query_fingerprint':'q','observed_at':'2026-09-15T00:00:00Z','expires_at':'2026-09-15T03:00:00Z','coverage_allowed':True},{'provider':'p2','kind':'LIVE_OFFER','price':10100,'query_fingerprint':'q','observed_at':'2026-09-15T00:00:00Z','expires_at':'2026-09-15T03:00:00Z','coverage_allowed':True}]
    assert run_cli('multi-provider',{'evidence':ev,'now':'2026-09-15T01:00:00Z'})['state']=='CONFIRMED'
    ev[1]['query_fingerprint']='other'; assert run_cli('multi-provider',{'evidence':ev,'now':'2026-09-15T01:00:00Z'})['state']=='PROBABLE'
