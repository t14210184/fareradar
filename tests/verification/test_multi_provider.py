def test_independent_live_sources_must_match(run_cli):
    ev=[{'provider':'p1','kind':'LIVE_OFFER','price':10000,'query_fingerprint':'q','observed_at':'2026-09-15T00:00:00Z','expires_at':'2026-09-15T03:00:00Z','coverage_allowed':True},{'provider':'p2','kind':'LIVE_OFFER','price':10100,'query_fingerprint':'q','observed_at':'2026-09-15T00:00:00Z','expires_at':'2026-09-15T03:00:00Z','coverage_allowed':True}]
    assert run_cli('multi-provider',{'evidence':ev,'now':'2026-09-15T01:00:00Z'})['state']=='CONFIRMED'
    ev[1]['query_fingerprint']='other'; assert run_cli('multi-provider',{'evidence':ev,'now':'2026-09-15T01:00:00Z'})['state']=='PROBABLE'


def test_live_offer_expiry_proactively_revokes_and_reprices():
    import json, pathlib, subprocess
    root=pathlib.Path(__file__).resolve().parents[2]
    p=subprocess.run(['node','tests/node_live_offer_expiry.mjs'],cwd=root,text=True,capture_output=True,check=True)
    x=json.loads(p.stdout)
    assert x['verifiedBefore']['verification_state']=='CONFIRMED' and x['verifiedBefore']['best_offer_id']=='offer-live-old'
    assert x['supportBefore']==[{'provider_offer_id':'offer-live-old','support_role':'PRIMARY'}]
    assert x['expiry']['processed']==1 and x['expiry']['reprice_state']=='ENQUEUED' and x['expiry']['correction_state']=='ENQUEUED'
    assert x['expiryQueries'] < 30
    assert x['verifiedExpired']=={'verification_state':'PROBABLE','reason':'SUPPORTING_LIVE_OFFER_EXPIRED','best_offer_id':None,'live_offer_count':0,'provider_count':0}
    assert x['supportExpired']==[]
    assert x['fareFacetExpired']['status']=='STALE' and x['fareFacetExpired']['reason_code']=='LIVE_OFFER_EXPIRED'
    assert x['lifecycle']['had_visible_notification']==1 and x['lifecycle']['reason']=='LIVE_OFFER_EXPIRED'
    assert x['correction']['payload']['kind']=='DEAL-UPDATE' and x['correction']['payload']['bookable'] is False
    assert len(x['refreshJobs'])==1 and ':refresh:' in x['refreshJobs'][0]['job_id'] and x['refreshJobs'][0]['state']=='PENDING'
    assert len(x['refreshConsumers'])==1
    assert x['oldNotice']['state']=='DELIVERED'
    assert x['pendingNotice']=={'state':'CANCELLED','last_error':'LIVE_OFFER_EXPIRED'}
    assert x['unprojected']['projected_at']=='2026-09-15T01:00:01Z'
    assert x['replay']['processed']==0 and x['replay']['resumed']==0
    assert x['refreshed']['state']=='DONE'
    assert x['verifiedAfter']['verification_state']=='CONFIRMED' and x['verifiedAfter']['best_offer_id']=='offer-live-new' and x['verifiedAfter']['best_offer_total']==5199
    assert x['supportAfter']==[{'provider_offer_id':'offer-live-new','support_role':'PRIMARY'}]
    assert x['fareFacetAfter']['status']=='PASS' and x['costAfter']['source_offer_id']=='offer-live-new' and x['costAfter']['amount']==5199


def test_live_offer_expiry_rotates_to_redundant_fresh_support_without_false_correction():
    import json, pathlib, subprocess
    root=pathlib.Path(__file__).resolve().parents[2]
    p=subprocess.run(['node','tests/node_live_offer_expiry_redundant.mjs'],cwd=root,text=True,capture_output=True,check=True)
    x=json.loads(p.stdout)
    assert x['out']['processed']==1 and x['out']['preserved_confirmation'] is True
    assert x['out']['correction_state']=='NOT_REQUIRED' and x['out']['reprice_state']=='NOT_REQUIRED'
    assert x['result']['verification_state']=='CONFIRMED' and x['result']['reason']=='INDEPENDENT_LIVE_MATCH'
    assert x['result']['best_offer_id']=='offer2' and x['result']['live_offer_count']==2 and x['result']['provider_count']==2
    assert x['supports']==[{'provider_offer_id':'offer2','support_role':'PRIMARY'},{'provider_offer_id':'offer3','support_role':'SUPPORT'}]
    assert x['event']=={'new_verification_state':'CONFIRMED','correction_state':'NOT_REQUIRED','reprice_state':'NOT_REQUIRED'}
    assert x['alerts']==0 and x['jobs']==0
