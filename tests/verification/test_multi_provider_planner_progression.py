import json, pathlib, subprocess
ROOT=pathlib.Path(__file__).resolve().parents[2]
def test_pending_signal_progresses_across_unused_provider_campaigns_without_bruteforce():
    p=subprocess.run(['node','tests/node_multi_provider_progression.mjs'],cwd=ROOT,text=True,capture_output=True,check=True)
    x=json.loads(p.stdout)
    assert x['first']['campaign_id']=='c1' and x['first']['created']==1
    assert x['second']['campaign_id']=='c2' and x['second']['created']==1
    assert x['third']['created']==0 and x['third']['reason']=='NO_MATCHING_CAMPAIGN'
    assert x['campaigns']==['c1','c2']
