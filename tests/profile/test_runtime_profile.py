import json, pathlib, subprocess
ROOT=pathlib.Path(__file__).resolve().parents[2]
def run():
    p=subprocess.run(['node','tests/node_profile_runtime.mjs'],cwd=ROOT,text=True,capture_output=True,check=True)
    return json.loads(p.stdout.strip().splitlines()[-1])
def test_private_runtime_profile_drives_baggage_query_and_query_fingerprint_input():
    x=run(); assert x['stored']=={'profile_id':'synthetic-return','checked_bag_pattern':'RETURN_ONLY','baggage_kg':20,'seat_required':0}
    assert x['query']['baggage_query']=={'checked_bags_by_slice':[0,1],'checked_bag_kg':20,'seat_required':False}
    assert x['roundtrip']['checked_bags_by_slice']==[0,1]
def test_return_only_profile_does_not_invent_checked_bag_for_one_way():
    assert run()['oneway']['checked_bags_by_slice']==[0]
def test_campaign_requires_existing_private_profile():
    assert run()['missing']=='RUNTIME_PROFILE_NOT_FOUND'
