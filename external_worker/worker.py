from __future__ import annotations
import hashlib,hmac,ipaddress,json,re,socket,time,urllib.parse,urllib.request,urllib.error
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
    if not (routes or prices or keywords): return None
    return {'extraction_type':'PROMOTION_SIGNAL','structured_payload':{'market':'TW','routes':sorted(set(routes)),'prices':prices,'promo_code':m.group(1).upper() if m else None,'keywords':keywords,'source_id':source_id}}
def sign_headers(secret:str,body:str):
    ts=str(int(time.time()*1000)); sig=hmac.new(secret.encode(),f'{ts}.{body}'.encode(),hashlib.sha256).hexdigest(); return {'x-fare-timestamp':ts,'x-fare-signature':sig,'content-type':'application/json'}
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
