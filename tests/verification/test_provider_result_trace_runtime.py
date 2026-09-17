import json, pathlib, subprocess
ROOT=pathlib.Path(__file__).resolve().parents[2]

def test_provider_offers_trace_back_to_signal_and_confirm_only_after_independent_live_match():
    p=subprocess.run(['node','tests/node_provider_result_trace.mjs'],cwd=ROOT,text=True,capture_output=True,check=True)
    x=json.loads(p.stdout)
    assert x['first']['state']=='DONE' and x['afterFirst']=={'verification_state':'PROBABLE','reason':'SINGLE_LIVE_SOURCE','live_offer_count':1,'provider_count':1}
    assert x['stateAfterFirst']=='PENDING'
    assert x['second']['state']=='DONE'
    assert x['final']['verification_state']=='CONFIRMED' and x['final']['reason']=='INDEPENDENT_LIVE_MATCH'
    assert x['final']['best_offer_id']=='offer-p1' and x['final']['best_offer_total']==5000
    assert x['final']['live_offer_count']==2 and x['final']['provider_count']==2 and x['state']=='DONE'
    assert x['links']==[{'provider_offer_id':'offer-p1','job_id':'job1'},{'provider_offer_id':'offer-p2','job_id':'job2'}]
    assert x['linksAfterReplay']==2
