import json
from provider_worker import duffel
from provider_worker import worker as pw

QUERY={'slices':[{'origin':'TPE','destination':'KIX','departure_date':'2026-11-03'}],'passengers':[{'type':'adult'}],'cabin_class':'economy','max_connections':1,'market':'TW','locale':'zh-TW','baggage_query':{'checked':1}}

def test_duffel_v2_request_and_normalization():
    seen={}
    def transport(url,headers,body):
        seen.update(url=url,headers=headers,payload=json.loads(body))
        return {'data':{'id':'orq_1','offers':[{'id':'off_1','total_currency':'TWD','total_amount':'5999.00','expires_at':'2026-09-15T01:00:00Z','slices':[{'segments':[{'origin':{'iata_code':'TPE'},'destination':{'iata_code':'KIX'},'departing_at':'2026-11-03T01:00:00Z','arriving_at':'2026-11-03T03:30:00Z','marketing_carrier':{'iata_code':'MM'},'operating_carrier':{'iata_code':'MM'},'marketing_carrier_flight_number':'001'}]}]}]}}
    out=duffel.search(QUERY,'token-x',transport)
    assert seen['url'].startswith('https://api.duffel.com/air/offer_requests?return_offers=true')
    assert seen['headers']['Duffel-Version']=='v2' and seen['headers']['Authorization']=='Bearer token-x'
    assert seen['payload']=={'data':{'slices':QUERY['slices'],'passengers':QUERY['passengers'],'cabin_class':'economy','max_connections':1}}
    snap=duffel.normalize_offer(out['offers'][0],QUERY,'qfp','job1','2026-09-15T00:00:00Z')
    assert snap['provider']=='duffel' and snap['provider_offer_id']=='off_1' and snap['offer_total']==5999.0
    assert snap['cached_or_live']=='LIVE' and len(snap['raw_sha256'])==64
    assert snap['offer_structure']['slices'][0]['segments'][0]['origin']=='TPE' and snap['offer_structure']['slices'][0]['segments'][0]['marketing_carrier']=='MM'

def test_provider_worker_heartbeat_no_credentials_does_not_lease():
    calls=[]
    def cloud(base,path,payload,secret): calls.append((path,payload)); return {}
    out=pw.run_once('https://fare.example','s',None,'w1',cloud_post=cloud)
    assert out==[{'status':'NO_CREDENTIALS'}]
    assert [c[0] for c in calls]==['/providers/runtime/readback']
    assert calls[0][1]['credentials_present'] is False

def test_provider_worker_ingests_live_offers_then_completes():
    calls=[]
    job={'job_id':'job1','query_fingerprint':'qfp','payload_json':json.dumps({'query':QUERY,'query_fingerprint':'qfp'})}
    def cloud(base,path,payload,secret):
        calls.append((path,payload))
        if path=='/provider-jobs/lease': return {'jobs':[job]}
        return {'ok':True}
    def transport(url,headers,body):return {'data':{'id':'orq_1','offers':[{'id':'off_2','total_currency':'TWD','total_amount':'4888.00','expires_at':'2026-09-15T01:00:00Z'}]}}
    out=pw.run_once('https://fare.example','s','token','w1',cloud_post=cloud,duffel_transport=transport)
    assert out[0]['status']=='DONE' and out[0]['offers']==['off_2']
    paths=[x[0] for x in calls]
    assert paths==['/providers/runtime/readback','/provider-jobs/lease','/offers/ingest','/provider-jobs/complete']
    offer=[x[1] for x in calls if x[0]=='/offers/ingest'][0]
    assert offer['provider']=='duffel' and offer['cached_or_live']=='LIVE' and offer['offer_total']==4888.0
