import json,pathlib,subprocess
ROOT=pathlib.Path(__file__).resolve().parents[2]
def test_observation_to_discovered_promotion_and_route():
    p=subprocess.run(['node','tests/node_source_projection.mjs'],cwd=ROOT,text=True,capture_output=True,check=True); x=json.loads(p.stdout)
    assert x['promotions']==1 and x['evidence']==1 and x['pstate']=='DISCOVERED'
    assert x['priority_count']==1
    assert x['priority']=={'required_verification':'LIVE_REPRICE','priority_score':70.0,'state':'PENDING'}
    assert x['routes']==1 and x['route_state']=='DISCOVERED'
    assert x['route_entries']==1 and x['route_entry_status']=='DISCOVERED'
    assert x['domain']==2 and x['privateBlocked'] is True
