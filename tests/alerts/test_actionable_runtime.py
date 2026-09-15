import json, pathlib, subprocess
ROOT=pathlib.Path(__file__).resolve().parents[2]

def test_actionable_and_alert_content_are_server_derived_and_fail_closed():
    p=subprocess.run(['node','tests/node_actionable_runtime.mjs'],cwd=ROOT,text=True,capture_output=True,check=True)
    x=json.loads(p.stdout)
    assert x['good']['status']==202 and x['good']['body']['actionable'] is True and x['good']['body']['queued'] is True
    assert x['stale']['status']==200 and x['stale']['body']['queued'] is False and x['stale']['body']['reason']=='READINESS_NOT_PASS'
    assert x['prob']['status']==200 and x['prob']['body']['queued'] is False and x['prob']['body']['reason']=='FARE_NOT_CONFIRMED'
    assert x['nocost']['status']==200 and x['nocost']['body']['queued'] is False and x['nocost']['body']['reason']=='COST_NOT_COMPLETE'
    assert x['forged']['status']==400 and x['forged']['body']['error']=='CLIENT_ACTIONABLE_FORBIDDEN'
    assert x['forgedPayload']['status']==400 and x['forgedPayload']['body']['error']=='CLIENT_ALERT_CONTENT_FORBIDDEN'
    assert x['provisional']['status']==202 and x['provisional']['body']['queued'] is True and x['provisional']['body']['provisional'] is True
    assert x['admin']['status']==400 and x['admin']['body']['error']=='CANDIDATE_ALERT_CLASS_INVALID'
    assert len(x['rows'])==2
    final=[r for r in x['rows'] if r['intent_id'].startswith('deal:')][0]['payload']
    assert final['cash_trip_cost_twd']==9900 and final['kind']=='P0-ACTIONABLE'
    assert final['tickets'][0]['provider']=='provider-a'
    assert 'cash_trip_cost_twd' not in x['good']['body']
