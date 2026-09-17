import json, pathlib, subprocess
ROOT=pathlib.Path(__file__).resolve().parents[2]
def test_member_and_channel_requirements_gate_provider_planning():
    p=subprocess.run(['node','tests/node_promotion_entitlements.mjs'],cwd=ROOT,text=True,capture_output=True,check=True)
    x=json.loads(p.stdout)
    assert x['missingBoth']['reason']=='PROMOTION_ENTITLEMENT_MISSING'
    assert set(x['missingBoth']['missing'])=={'MEMBER:TEAM_TIGER','CHANNEL:APP_ONLY'}
    assert x['missingChannel']['reason']=='PROMOTION_ENTITLEMENT_MISSING' and x['missingChannel']['missing']==['CHANNEL:APP_ONLY']
    assert x['allowed']['created']>0 and x['plans']==x['allowed']['created']
    assert x['active']=={'allowed':True,'missing':[]}
    assert x['expired']['allowed'] is False
    assert x['publicAccess']=={'allowed':True,'missing':[]}
