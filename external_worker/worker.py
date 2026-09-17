from __future__ import annotations
import hashlib,hmac,ipaddress,json,os,re,secrets,socket,time,urllib.parse,urllib.request,urllib.error
MAX_BODY=2_000_000
ALLOWED_MIME=('text/','application/json','application/xml','application/rss+xml','application/atom+xml')
def _public_ip(ip:str)->bool:
    x=ipaddress.ip_address(ip); return not (x.is_private or x.is_loopback or x.is_link_local or x.is_multicast or x.is_reserved or x.is_unspecified)
def validate_url(url:str):
    u=urllib.parse.urlparse(url)
    if u.scheme!='https' or not u.hostname: raise ValueError('HTTPS_REQUIRED')
    infos=socket.getaddrinfo(u.hostname,u.port or 443,type=socket.SOCK_STREAM)
    if not infos or any(not _public_ip(i[4][0]) for i in infos): raise ValueError('SSRF_BLOCKED')
    return True
def structured_signal(text:str,source_id:str):
    routes=[]
    for a,b in re.findall(r'\b(TPE|KHH|RMQ|TSA)\s*(?:-|–|→|to|至)\s*([A-Z]{3})\b',text,re.I): routes.append(f'{a.upper()}-{b.upper()}')
    prices=[]
    # separate patterns keep currency explicit
    for cur,pat in [('TWD',r'(?:NT\$|TWD\s*)([0-9][0-9,]{2,})'),('JPY',r'(?:JPY\s*|¥\s*)([0-9][0-9,]{2,})')]:
        for n in re.findall(pat,text,re.I): prices.append({'currency':cur,'amount':int(n.replace(',',''))})
    m=re.search(r'(?:優惠碼|折扣碼|promo\s*code)\s*[:：]?\s*([A-Z0-9_-]{3,20})',text,re.I)
    keywords=[k for k in ['特價','促銷','清艙','清倉','限時','flash sale','sale'] if k.lower() in text.lower()]
    member_requirement='TEAM_TIGER' if re.search(r'team\s*tiger|尊榮虎',text,re.I) else ('MEMBER_ONLY' if re.search(r'(?:會員(?:限定|專屬)|member[-\s]?only)',text,re.I) else None)
    channel_requirements=[]
    if '樂虎卡' in text: channel_requirements.append('LOHO_CARD')
    if re.search(r'(?:app\s*(?:only|限定)|APP限定)',text,re.I): channel_requirements.append('APP_ONLY')
    if re.search(r'(?:line\s*(?:only|限定)|LINE限定)',text,re.I): channel_requirements.append('LINE_ONLY')
    channel_requirement='+'.join(sorted(set(channel_requirements))) if channel_requirements else None
    flights=[]
    for block in re.findall(r'(?:航班|班機|flight(?:s)?(?:\s*no\.?)?)\s*[:：#]?\s*((?:[A-Z0-9]{2}\s?\d{2,4})(?:\s*[/、,，]\s*[A-Z0-9]{2}\s?\d{2,4})*)',text,re.I):
        flights.extend(re.sub(r'\s+','',x).upper() for x in re.findall(r'[A-Z0-9]{2}\s?\d{2,4}',block,re.I))
    flights.extend(x.upper() for x in re.findall(r'\b([A-Z0-9]{2}\d{2,4})\b\s*(?:航班|班機)',text,re.I))
    required_roundtrip=bool(re.search(r'(?:限|僅限|須|需).{0,6}(?:來回|round[\s-]?trip)|(?:來回|round[\s-]?trip).{0,6}(?:限定|only|must)',text,re.I))
    coupon_required=bool(m or re.search(r'(?:須|需|請).{0,5}(?:輸入|使用).{0,5}(?:優惠碼|折扣碼|promo\s*code)',text,re.I))
    currencies=sorted(set(x['currency'] for x in prices)); sales_currency=currencies[0] if len(currencies)==1 else None
    if not (routes or prices or keywords): return None
    return {'extraction_type':'PROMOTION_SIGNAL','structured_payload':{'market':'TW','routes':sorted(set(routes)),'prices':prices,'promo_code':m.group(1).upper() if m else None,'keywords':keywords,'member_requirement':member_requirement,'channel_requirement':channel_requirement,'eligible_flight_numbers':sorted(set(flights)),'required_roundtrip':required_roundtrip,'coupon_required':coupon_required,'sales_currency':sales_currency,'source_id':source_id}}
def sign_headers(secret:str,body:str,path:str,method:str='POST',key_id:str|None=None,nonce:str|None=None,ts:str|None=None):
    ts=ts or str(int(time.time()*1000)); key_id=key_id or os.environ.get('FARE_HMAC_KEY_ID')
    if not key_id:
        if os.environ.get('FARE_ALLOW_LEGACY_INGEST_TOKEN')=='1':
            sig=hmac.new(secret.encode(),f'{ts}.{body}'.encode(),hashlib.sha256).hexdigest()
            return {'x-fare-timestamp':ts,'x-fare-signature':sig,'content-type':'application/json'}
        raise ValueError('FARE_HMAC_KEY_ID_REQUIRED')
    nonce=nonce or secrets.token_urlsafe(24)
    body_hash=hashlib.sha256(body.encode()).hexdigest()
    canonical='\n'.join([key_id,ts,nonce,method.upper(),path,body_hash])
    sig=hmac.new(secret.encode(),canonical.encode(),hashlib.sha256).hexdigest()
    return {'x-fare-key-id':key_id,'x-fare-timestamp':ts,'x-fare-nonce':nonce,'x-fare-signature':sig,'content-type':'application/json'}
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs): return None
def fetch(url:str,etag:str|None=None,last_modified:str|None=None,max_redirects=5):
    current=url
    for _ in range(max_redirects+1):
        validate_url(current); headers={'User-Agent':'FareRadar/1.3 (+source-monitor)'}
        if etag:headers['If-None-Match']=etag
        if last_modified:headers['If-Modified-Since']=last_modified
        req=urllib.request.Request(current,headers=headers); opener=urllib.request.build_opener(NoRedirect)
        try:r=opener.open(req,timeout=20)
        except urllib.error.HTTPError as e:r=e
        if r.status in (301,302,303,307,308):
            loc=r.headers.get('Location');
            if not loc:raise ValueError('REDIRECT_WITHOUT_LOCATION')
            current=urllib.parse.urljoin(current,loc); continue
        if r.status==304:return {'status':304,'url':current,'not_modified':True}
        if r.status!=200:raise ValueError(f'HTTP_{r.status}')
        ctype=(r.headers.get('Content-Type') or '').split(';',1)[0].strip().lower()
        if not any(ctype.startswith(x) for x in ALLOWED_MIME):raise ValueError('MIME_BLOCKED')
        body=r.read(MAX_BODY+1)
        if len(body)>MAX_BODY:raise ValueError('BODY_TOO_LARGE')
        text=body.decode('utf-8','replace')
        return {'status':200,'url':current,'body':text,'content_sha256':hashlib.sha256(body).hexdigest(),'etag':r.headers.get('ETag'),'last_modified':r.headers.get('Last-Modified'),'content_type':ctype}
    raise ValueError('TOO_MANY_REDIRECTS')

def post_json(base_url:str,path:str,payload:dict,secret:str):
    body=json.dumps(payload,separators=(',',':'),ensure_ascii=False)
    req=urllib.request.Request(base_url.rstrip('/')+path,data=body.encode(),headers=sign_headers(secret,body,path,'POST'),method='POST')
    with urllib.request.urlopen(req,timeout=20) as r:
        return json.loads(r.read().decode())


def post_worker_json(base_url:str,path:str,payload:dict,worker_token:str):
    body=json.dumps(payload,separators=(',',':'),ensure_ascii=False)
    req=urllib.request.Request(base_url.rstrip('/')+path,data=body.encode(),headers={'x-fare-worker-token':worker_token,'content-type':'application/json'},method='POST')
    with urllib.request.urlopen(req,timeout=20) as r:
        return json.loads(r.read().decode())

def observation_id(source_id:str,url:str,content_sha256:str):
    return hashlib.sha256(f'{source_id}|{url}|{content_sha256}'.encode()).hexdigest()

def run_once(base_url:str,worker_token:str,worker_id:str):
    leased=post_worker_json(base_url,'/verification-jobs/lease',{'worker_id':worker_id,'limit':5},worker_token).get('jobs',[])
    results=[]
    for job in leased:
        payload=json.loads(job['payload_json']); source_id=payload['source_id']; url=payload['url']
        try:
            got=fetch(url)
            if got.get('not_modified'):
                post_worker_json(base_url,'/verification-jobs/complete',{'job_id':job['job_id'],'worker_id':worker_id,'source_id':source_id,'success':True,'duplicate':True},worker_token); results.append({'job_id':job['job_id'],'status':'NOT_MODIFIED'}); continue
            signal=structured_signal(got['body'],source_id)
            obs={'observation_id':observation_id(source_id,got['url'],got['content_sha256']),'source_id':source_id,'worker_id':worker_id,'lease_job_id':job['job_id'],'observed_at':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'canonical_url':got['url'],'content_sha256':got['content_sha256'],'parser_version':'external-worker-1','privacy_class':'PUBLIC'}
            if signal: obs.update(signal)
            post_worker_json(base_url,'/ingest',obs,worker_token)
            post_worker_json(base_url,'/verification-jobs/complete',{'job_id':job['job_id'],'worker_id':worker_id,'source_id':source_id,'success':True,'etag':got.get('etag'),'last_modified':got.get('last_modified'),'content_sha256':got['content_sha256']},worker_token)
            results.append({'job_id':job['job_id'],'status':'DONE'})
        except Exception as e:
            try: post_worker_json(base_url,'/verification-jobs/complete',{'job_id':job['job_id'],'worker_id':worker_id,'source_id':source_id,'success':False,'error':type(e).__name__+':'+str(e)[:300],'schema_drift':str(e)=='MIME_BLOCKED'},worker_token)
            finally: results.append({'job_id':job['job_id'],'status':'FAILED','error':str(e)})
    return results

if __name__=='__main__':
    import sys
    base=os.environ.get('FARE_RADAR_BASE_URL'); worker_token=os.environ.get('FARE_RADAR_WORKER_TOKEN'); wid=os.environ.get('FARE_WORKER_ID',socket.gethostname())
    if not base or not worker_token: raise SystemExit('FARE_RADAR_BASE_URL and FARE_RADAR_WORKER_TOKEN required')
    once='--once' in sys.argv
    while True:
        run_once(base,worker_token,wid)
        if once: break
        time.sleep(30)
