import json, pathlib, subprocess
ROOT=pathlib.Path(__file__).resolve().parents[2]
def test_shadow_deals_are_permanently_held_and_admin_remains_deliverable():
    p=subprocess.run(['node','tests/node_shadow_notification_fence.mjs'],cwd=ROOT,text=True,capture_output=True,check=True)
    x=json.loads(p.stdout)
    assert x['states1']==[{'notification_id':'shadow-admin','state':'PENDING'},{'notification_id':'shadow-deal','state':'SHADOW_HELD'}]
    assert x['leasedShadow']==['shadow-admin']
    assert x['leasedProd']==['prod-deal']
    assert [r for r in x['states2'] if r['notification_id']=='shadow-deal'][0]['state']=='SHADOW_HELD'
