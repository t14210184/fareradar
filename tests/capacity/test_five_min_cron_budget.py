import json, pathlib, subprocess
ROOT=pathlib.Path(__file__).resolve().parents[2]
def test_five_min_planner_and_provisional_stay_below_d1_query_budget():
    p=subprocess.run(['node','tests/node_five_min_cron_budget.mjs'],cwd=ROOT,text=True,capture_output=True,check=True)
    x=json.loads(p.stdout)
    assert x['queries'] <= 50
    assert x['provisional']=={'considered':1,'triggered':1}
    assert x['expired']=={'expired':1}
    assert x['intents']==2
