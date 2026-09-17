import json,pathlib,subprocess
ROOT=pathlib.Path(__file__).resolve().parents[2]
def test_historical_baseline_is_dimensioned_and_fail_closed():
    p=subprocess.run(['node','tests/node_historical_baseline.mjs'],cwd=ROOT,text=True,capture_output=True,check=True)
    x=json.loads(p.stdout)
    assert x['projected']['claimed']==11 and x['projected']['done']==11
    assert x['current']['ready'] is True and x['current']['sample_count']==5
    assert x['current']['median']==7000 and x['current']['p10']==6800
    assert x['round']['ready'] is False and x['round']['reason']=='BASELINE_SAMPLE_INSUFFICIENT'
    assert x['cached']['ready'] is False and x['cached']['reason']=='BASELINE_OBSERVATION_MISSING'
    assert x['count']==9  # includes future baseline observation, but current comparator must not use it
    assert x['futureIncluded'] is True
    assert any(r['trip_type']=='ROUNDTRIP' for r in x['rows'])
    assert any('bags:1' in r['baggage_profile'] for r in x['rows'])
