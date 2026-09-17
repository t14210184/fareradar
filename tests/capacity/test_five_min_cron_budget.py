import json, pathlib, subprocess
ROOT=pathlib.Path(__file__).resolve().parents[2]

def run(mode):
    p=subprocess.run(['node','tests/node_five_min_cron_budget.mjs',mode],cwd=ROOT,text=True,capture_output=True,check=True)
    return json.loads(p.stdout)

def test_five_min_full_path_stays_within_internal_40_query_target():
    x=run('no-expiry')
    assert x['queries'] <= 40
    assert x['expired']=={'expired':0}
    assert x['liveExpiry']=={'processed':0,'resumed':0}
    assert x['provisional']=={'considered':1,'triggered':1}
    assert x['intents']==1

def test_five_min_expiry_lifecycle_preempts_optional_work():
    x=run('agency-expiry')
    assert x['queries'] <= 40
    assert x['expired']=={'expired':1}
    assert x['liveExpiry'] is None and x['planned'] is None and x['provisional'] is None
    assert x['intents']==1
