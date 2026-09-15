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
    detail_seen={}
    def detail_transport(url,headers):
        detail_seen.update(url=url,headers=headers)
        return {'data':{'id':'off_1','total_currency':'TWD','total_amount':'6099.00','expires_at':'2026-09-15T01:00:00Z','available_services':[{'id':'ase_1','type':'baggage','total_currency':'TWD','total_amount':'900.00','segment_ids':['seg1'],'passenger_ids':['pas1'],'maximum_quantity':1}],'slices':[{'segments':[{'id':'seg1','origin':{'iata_code':'TPE'},'destination':{'iata_code':'KIX'},'departing_at':'2026-11-03T01:00:00Z','arriving_at':'2026-11-03T03:30:00Z','marketing_carrier':{'iata_code':'MM'},'operating_carrier':{'iata_code':'MM'},'marketing_carrier_flight_number':'001','passengers':[{'passenger_id':'pas1','baggages':[]}]}]}]}}
    detail=duffel.refresh_offer('off_1','token-x',detail_transport)
    snap=duffel.normalize_offer(detail,QUERY,'qfp','job1','2026-09-15T00:00:00Z','REFRESHED_LIVE')
    assert detail_seen['url']=='https://api.duffel.com/air/offers/off_1?return_available_services=true'
    assert detail_seen['headers']['Duffel-Version']=='v2' and detail_seen['headers']['Authorization']=='Bearer token-x'
    assert snap['provider']=='duffel' and snap['provider_offer_id']=='off_1' and snap['offer_total']==6099.0
    assert snap['cached_or_live']=='LIVE' and snap['fare_freshness']=='REFRESHED_LIVE' and len(snap['raw_sha256'])==64
    assert snap['offer_structure']['price_scope']=='FLIGHT_TOTAL_INCLUDES_TAX_EXCLUDES_SERVICES'
    assert snap['offer_structure']['available_services'][0]['type']=='baggage' and snap['offer_structure']['available_services'][0]['total_amount']=='900.00'
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
    def detail_transport(url,headers):return {'data':{'id':'off_2','total_currency':'TWD','total_amount':'4999.00','expires_at':'2026-09-15T01:00:00Z','available_services':[],'slices':[{'segments':[{'id':'seg2','origin':{'iata_code':'TPE'},'destination':{'iata_code':'KIX'},'departing_at':'2026-11-03T01:00:00Z','arriving_at':'2026-11-03T03:30:00Z','marketing_carrier':{'iata_code':'MM'},'operating_carrier':{'iata_code':'MM'},'marketing_carrier_flight_number':'002','passengers':[]}]}]}}
    out=pw.run_once('https://fare.example','s','token','w1',cloud_post=cloud,duffel_transport=transport,duffel_detail_transport=detail_transport)
    assert out[0]['status']=='DONE' and out[0]['offers']==['off_2']
    paths=[x[0] for x in calls]
    assert paths==['/providers/runtime/readback','/provider-jobs/lease','/offers/ingest','/provider-jobs/complete']
    offer=[x[1] for x in calls if x[0]=='/offers/ingest'][0]
    assert offer['provider']=='duffel' and offer['cached_or_live']=='LIVE' and offer['fare_freshness']=='REFRESHED_LIVE' and offer['offer_total']==4999.0


def test_provider_worker_refreshes_only_bounded_cheapest_offers():
    jobs={'job_id':'job-b','query_fingerprint':'qfp-b','payload_json':json.dumps({'query':QUERY,'query_fingerprint':'qfp-b'})}
    calls=[]; refreshed=[]
    def cloud(base,path,payload,secret):
        calls.append((path,payload))
        if path=='/provider-jobs/lease': return {'jobs':[jobs]}
        return {'ok':True}
    def search_transport(url,headers,body):
        return {'data':{'id':'orq-b','offers':[{'id':f'off_{i}','total_currency':'TWD','total_amount':str(v),'expires_at':'2026-09-15T01:00:00Z'} for i,v in enumerate([6000,5000,7000,4000,3000])]}}
    def detail_transport(url,headers):
        oid=url.split('/air/offers/')[1].split('?')[0]; refreshed.append(oid); amount={'off_0':'6000','off_1':'5000','off_2':'7000','off_3':'4000','off_4':'3000'}[oid]
        return {'data':{'id':oid,'total_currency':'TWD','total_amount':amount,'expires_at':'2026-09-15T01:00:00Z','available_services':[],'slices':[{'segments':[{'id':'s','origin':{'iata_code':'TPE'},'destination':{'iata_code':'KIX'},'departing_at':'2026-11-03T01:00:00Z','arriving_at':'2026-11-03T03:30:00Z'}]}]}}
    out=pw.run_once('https://fare.example','s','token','w1',cloud_post=cloud,duffel_transport=search_transport,duffel_detail_transport=detail_transport)
    assert refreshed==['off_4','off_3','off_1']
    assert out[0]['offers']==['off_4','off_3','off_1']

def test_duffel_price_action_uses_card_and_services_but_quote_drops_card_id():
    seen={}
    def transport(url,headers,body):
        seen.update(url=url,headers=headers,payload=json.loads(body))
        return {'data':{'id':'off_price','total_currency':'TWD','total_amount':'5900.00','expires_at':'2026-09-15T00:20:00Z','intended_payment_methods':[{'type':'card','card_id':'tcd_secret','surcharge_currency':'TWD','surcharge_amount':'100.00'}],'intended_services':[{'id':'ase_1','quantity':1}]}}
    data=duffel.price_offer('off_price','token-x',[{'id':'ase_1','quantity':1}],'tcd_secret',transport)
    quote=duffel.normalize_price_quote(data,'off_price','pay1',[{'id':'ase_1','quantity':1}],'job-price','2026-09-15T00:02:00Z')
    assert seen['url']=='https://api.duffel.com/air/offers/off_price/actions/price'
    assert seen['payload']['data']['intended_payment_methods']==[{'type':'card','card_id':'tcd_secret'}]
    assert seen['payload']['data']['intended_services']==[{'id':'ase_1','quantity':1}]
    assert quote['fare_and_services_total']==5900.0 and quote['surcharge_total']==100.0 and quote['grand_total']==6000.0
    assert 'card_id' not in json.dumps(quote)

def test_provider_worker_checkout_job_requires_private_card_binding_and_ingests_quote():
    job={'job_id':'checkout-1','job_type':'CHECKOUT_REPRICE','query_fingerprint':'q1','payload_json':json.dumps({'provider_offer_id':'off_price','payment_profile_id':'pay1','credential_binding':'DUFFEL_PAYMENT_CARD_ID','selected_services':[{'id':'ase_1','quantity':1}]})}
    calls=[]
    def cloud(base,path,payload,secret):
        calls.append((path,payload))
        if path=='/provider-jobs/lease': return {'jobs':[job]}
        return {'ok':True}
    def resolver(name): return 'tcd_private' if name=='DUFFEL_PAYMENT_CARD_ID' else None
    def price_transport(url,headers,body): return {'data':{'id':'off_price','total_currency':'TWD','total_amount':'5900.00','intended_payment_methods':[{'type':'card','card_id':'tcd_private','surcharge_currency':'TWD','surcharge_amount':'100.00'}],'intended_services':[{'id':'ase_1','quantity':1}]}}
    out=pw.run_once('https://fare.example','s','token','w1',cloud_post=cloud,duffel_price_transport=price_transport,credential_resolver=resolver)
    assert out[0]['status']=='DONE' and out[0]['quote_id'].startswith('price:off_price:')
    heartbeat=calls[0][1]; assert 'CHECKOUT_REPRICE' in heartbeat['capabilities']
    leased=calls[1][1]; assert 'CHECKOUT_REPRICE' in leased['verification_types']
    quote=[x[1] for x in calls if x[0]=='/pricing-quotes/ingest'][0]
    assert quote['grand_total']==6000.0 and 'tcd_private' not in json.dumps(quote)
