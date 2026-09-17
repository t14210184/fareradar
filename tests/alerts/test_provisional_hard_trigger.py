import json, pathlib, subprocess
ROOT=pathlib.Path(__file__).resolve().parents[2]

def test_server_side_provisional_requires_baseline_trust_and_route_relevance():
    p=subprocess.run(['node','tests/node_provisional_hard_trigger.mjs'],cwd=ROOT,text=True,capture_output=True,check=True)
    x=json.loads(p.stdout)
    assert x['positive']['triggered'] is True
    assert x['positive']['reason']=='HISTORICAL_ANOMALY'
    assert x['positive']['baseline']['sample_count']==5
    assert x['positive']['baseline']['median']==7000
    assert abs(x['positive']['ratio']-(4000/7000))<1e-9
    assert x['positiveReplay']['triggered'] is True and x['intentCount']==1
    assert x['payload']['kind']=='P0-PROVISIONAL'
    assert x['payload']['provisional_trigger']['rule']=='HISTORICAL_ANOMALY_V1'
    assert x['payload']['provisional_trigger']['trusted_sources']==['s-trusted']
    assert x['shadow']['triggered'] is False and x['shadow']['reason']=='DISCOVERY_SOURCE_NOT_TRUSTED'
    assert x['insufficient']['triggered'] is False and x['insufficient']['reason']=='BASELINE_SAMPLE_INSUFFICIENT'
    assert x['routeMismatch']['triggered'] is False and x['routeMismatch']['reason']=='ROUTE_NOT_RELEVANT'
    assert x['dateMismatch']['triggered'] is False and x['dateMismatch']['reason']=='ROUTE_NOT_RELEVANT'
    assert x['expensive']['triggered'] is False and x['expensive']['reason']=='ANOMALY_THRESHOLD_NOT_MET'
    assert x['confirmed']['triggered'] is False and x['confirmed']['reason']=='NOT_PROBABLE'
