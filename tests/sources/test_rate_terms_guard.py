def test_terms_and_kill_switch_guard(run_cli):
    base={'terms_state':'CURRENT','access_valid':True,'kill_switch':False,'retry_after_until':None}
    assert run_cli('dispatch-allowed',{'policy':base,'now':'2026-09-15T00:00:00Z'}) is True
    bad=dict(base); bad['terms_state']='STALE'; assert run_cli('dispatch-allowed',{'policy':bad,'now':'2026-09-15T00:00:00Z'}) is False
    bad=dict(base); bad['kill_switch']=True; assert run_cli('dispatch-allowed',{'policy':bad,'now':'2026-09-15T00:00:00Z'}) is False
