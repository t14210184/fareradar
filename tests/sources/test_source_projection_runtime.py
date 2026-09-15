import json,pathlib,subprocess
ROOT=pathlib.Path(__file__).resolve().parents[2]
def test_observation_to_discovered_promotion_and_route():
    p=subprocess.run(['node','tests/node_source_projection.mjs'],cwd=ROOT,text=True,capture_output=True,check=True); x=json.loads(p.stdout)
    assert x['promotions']==1 and x['evidence']==1 and x['pstate']=='DISCOVERED'
    assert x['routes']==1 and x['route_state']=='DISCOVERED'
    assert x['domain']==2 and x['privateBlocked'] is True
