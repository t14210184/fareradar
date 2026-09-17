def test_event_time_effective_window_and_ttl(run_cli):
    p={'observed_at':'2026-09-15T00:00:00Z','effective_from':'2026-07-01T00:00:00Z','effective_to':None,'ttl_hours':48,'status':'CURRENT'}
    assert run_cli('policy-usable',{'policy':p,'event_at':'2026-10-01T00:00:00Z','now':'2026-09-15T12:00:00Z'}) is True
    assert run_cli('policy-usable',{'policy':p,'event_at':'2026-06-01T00:00:00Z','now':'2026-09-15T12:00:00Z'}) is False
    assert run_cli('policy-usable',{'policy':p,'event_at':'2026-10-01T00:00:00Z','now':'2026-09-18T12:00:00Z'}) is False
