import json,pathlib,subprocess
ROOT=pathlib.Path(__file__).resolve().parents[2]
def test_shadow_deals_are_held_and_never_released_by_mode_flip():
    p=subprocess.run(['node','tests/node_shadow_notification_fence.mjs'],cwd=ROOT,text=True,capture_output=True,check=True)
    x=json.loads(p.stdout)
    assert x['missing_mode']=='SHADOW_ACCEPTANCE' and x['bad_mode']=='SHADOW_ACCEPTANCE' and x['prod_mode']=='PRODUCTION'
    assert {r['notification_id']:r['state'] for r in x['shadowStates']}=={'shadow-admin':'PENDING','shadow-deal':'SHADOW_HELD'}
    assert x['shadowLease']==['shadow-admin']
    assert x['productionLease']==['production-deal']
    assert x['oldShadow']=='SHADOW_HELD'
