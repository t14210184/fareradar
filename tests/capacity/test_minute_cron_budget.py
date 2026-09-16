import json, pathlib, subprocess
ROOT=pathlib.Path(__file__).resolve().parents[2]

def test_minute_hot_path_stays_within_internal_40_query_target():
    p=subprocess.run(['node','tests/node_minute_cron_budget.mjs'],cwd=ROOT,text=True,capture_output=True,check=True)
    x=json.loads(p.stdout)
    assert x['queries'] <= 40
    assert x['projected']==10 and x['held']==10
    assert x['domain']=={'claimed':2,'done':2}
    assert x['sources']=={'considered':10,'inserted':10}
    assert x['jobs']==10
    assert x['steps']['projectAlertIntents'] <= 3
    assert x['steps']['scheduleDueSources'] <= 3
