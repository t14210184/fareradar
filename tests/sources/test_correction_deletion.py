def test_correction_and_delete_append_versions_without_overwrite(run_cli):
    h=[{'entity_id':'promo-1','version':1,'state':'ACTIVE','payload':{'price':3999},'observed_at':'2026-09-15T00:00:00Z'}]
    h=run_cli('apply-correction',{'history':h,'event':{'entity_id':'promo-1','type':'CORRECT','payload':{'price':4999},'observed_at':'2026-09-15T01:00:00Z'}})
    assert len(h)==2 and h[0]['payload']['price']==3999 and h[1]['version']==2 and h[1]['supersedes_version']==1
    h=run_cli('apply-correction',{'history':h,'event':{'entity_id':'promo-1','type':'DELETE','observed_at':'2026-09-15T02:00:00Z'}})
    assert len(h)==3 and h[-1]['state']=='DELETED' and h[-1]['payload'] is None
