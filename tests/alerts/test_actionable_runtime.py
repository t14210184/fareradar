import json, pathlib, subprocess
ROOT=pathlib.Path(__file__).resolve().parents[2]

def test_actionable_is_server_derived_and_fail_closed():
    p=subprocess.run(['node','tests/node_actionable_runtime.mjs'],cwd=ROOT,text=True,capture_output=True,check=True)
    x=json.loads(p.stdout)
    assert x['good']['status']==202 and x['good']['body']['actionable'] is True and x['good']['body']['queued'] is True
    assert x['stale']['status']==200 and x['stale']['body']['queued'] is False and x['stale']['body']['reason']=='READINESS_NOT_PASS'
    assert x['prob']['status']==200 and x['prob']['body']['queued'] is False and x['prob']['body']['reason']=='FARE_NOT_CONFIRMED'
    assert x['nocost']['status']==200 and x['nocost']['body']['queued'] is False and x['nocost']['body']['reason']=='COST_NOT_COMPLETE'
    assert x['forged']['status']==400 and x['forged']['body']['error']=='CLIENT_ACTIONABLE_FORBIDDEN'
    assert x['provisional']['status']==202 and x['provisional']['body']['queued'] is True and x['provisional']['body']['provisional'] is True
    assert x['admin']['status']==400 and x['admin']['body']['error']=='CANDIDATE_ALERT_CLASS_INVALID'
    assert x['intents']==2
