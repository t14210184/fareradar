from tests.fixtures import plan
def test_stale_policy_facet_blocks_actionable(run_cli):
    p=plan(); f=next(x for x in p['readiness'] if x['facet_type']=='POLICY_FRESH'); f['status']='STALE'
    assert run_cli('actionable',{'verification_state':'CONFIRMED','facets':p['readiness'],'at':'2026-09-15T00:30:00Z'}) is False
