from __future__ import annotations
import hashlib,hmac,json,os,socket,time,urllib.request
from . import duffel

def sign_headers(secret:str,body:str):
    ts=str(int(time.time()*1000)); sig=hmac.new(secret.encode(),f'{ts}.{body}'.encode(),hashlib.sha256).hexdigest(); return {'x-fare-timestamp':ts,'x-fare-signature':sig,'content-type':'application/json'}
def post_json(base_url:str,path:str,payload:dict,secret:str):
    body=json.dumps(payload,separators=(',',':'),ensure_ascii=False); req=urllib.request.Request(base_url.rstrip('/')+path,data=body.encode(),headers=sign_headers(secret,body),method='POST')
    with urllib.request.urlopen(req,timeout=25) as r:return json.loads(r.read().decode())

def run_once(base_url:str,secret:str,token:str|None,worker_id:str,cloud_post=post_json,duffel_transport=duffel.default_transport,duffel_detail_transport=duffel.default_get_transport):
    has_token=bool(token)
    cloud_post(base_url,'/providers/runtime/readback',{'provider_id':'duffel','worker_id':worker_id,'connector_version':'duffel-v2-1','credentials_present':has_token,'capabilities':['LIVE_REPRICE'],'ttl_seconds':300},secret)
    if not token:return [{'status':'NO_CREDENTIALS'}]
    leased=cloud_post(base_url,'/provider-jobs/lease',{'provider_id':'duffel','worker_id':worker_id,'limit':3},secret).get('jobs',[]); results=[]
    for job in leased:
        try:
            payload=json.loads(job['payload_json']); query=payload['query']; qfp=job.get('query_fingerprint') or payload['query_fingerprint']
            found=duffel.search(query,token,duffel_transport); now=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())
            normalized=[]
            for offer in sorted(found['offers'],key=lambda o:float(o.get('total_amount','inf')))[:3]:
                oid=offer.get('id')
                if not oid: continue
                try: detailed=duffel.refresh_offer(oid,token,duffel_detail_transport)
                except Exception: continue
                snap=duffel.normalize_offer(detailed,query,qfp,job['job_id'],now,'REFRESHED_LIVE'); cloud_post(base_url,'/offers/ingest',snap,secret); normalized.append(snap['provider_offer_id'])
            cloud_post(base_url,'/provider-jobs/complete',{'job_id':job['job_id'],'provider_id':'duffel','success':True},secret)
            results.append({'job_id':job['job_id'],'status':'DONE','offers':normalized})
        except Exception as e:
            try:cloud_post(base_url,'/provider-jobs/complete',{'job_id':job['job_id'],'provider_id':'duffel','success':False,'error':type(e).__name__+':'+str(e)[:300]},secret)
            finally:results.append({'job_id':job['job_id'],'status':'FAILED','error':str(e)})
    return results

if __name__=='__main__':
    base=os.environ.get('FARE_RADAR_BASE_URL'); secret=os.environ.get('FARE_INGEST_HMAC_SECRET'); token=os.environ.get('DUFFEL_ACCESS_TOKEN'); wid=os.environ.get('FARE_PROVIDER_WORKER_ID',socket.gethostname())
    if not base or not secret: raise SystemExit('FARE_RADAR_BASE_URL and FARE_INGEST_HMAC_SECRET required')
    once='--once' in os.sys.argv
    while True:
        run_once(base,secret,token,wid)
        if once:break
        time.sleep(30)
