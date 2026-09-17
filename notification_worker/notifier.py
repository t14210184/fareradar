from __future__ import annotations
import json,os,time,urllib.error,urllib.request
from external_worker.worker import post_json,validate_url

def send_webhook(url:str,payload:dict,notification_id:str,attempt:int):
    validate_url(url)
    body=json.dumps(payload,separators=(',',':'),ensure_ascii=False).encode()
    req=urllib.request.Request(url,data=body,headers={'content-type':'application/json','X-Fare-Notification-Id':notification_id,'X-Fare-Attempt':str(attempt)},method='POST')
    try:
        with urllib.request.urlopen(req,timeout=20) as r: status=r.status
    except urllib.error.HTTPError as e: status=e.code
    ok=200<=status<300; retryable=status in (408,425,429) or status>=500
    return {'ok':ok,'retryable':retryable,'status':status}

def run_once(base_url:str,secret:str,worker_id:str,deal_url:str|None,admin_url:str|None):
    jobs=post_json(base_url,'/notifications/lease',{'worker_id':worker_id,'limit':10},secret).get('jobs',[]); results=[]
    for j in jobs:
        nid=j['notification_id']; channel=j['channel_class']; attempt=int(j.get('attempts',1)); endpoint=admin_url if channel=='ADMIN' else deal_url if channel=='DEAL' else None
        if not endpoint:
            outcome={'ok':False,'retryable':False,'status':0,'error':'CHANNEL_NOT_CONFIGURED'}
        else:
            try: outcome=send_webhook(endpoint,json.loads(j['payload_json']),nid,attempt)
            except Exception as e: outcome={'ok':False,'retryable':True,'status':0,'error':type(e).__name__+':'+str(e)[:300]}
        ack={'notification_id':nid,'worker_id':worker_id,'ok':outcome['ok'],'retryable':outcome['retryable'],'error':None if outcome['ok'] else outcome.get('error') or f"HTTP_{outcome.get('status',0)}"}
        post_json(base_url,'/notifications/ack',ack,secret); results.append({'notification_id':nid,'channel':channel,**outcome})
    return results

if __name__=='__main__':
    import socket,sys
    base=os.environ.get('FARE_RADAR_BASE_URL'); secret=os.environ.get('FARE_HMAC_SECRET') or os.environ.get('FARE_INGEST_HMAC_SECRET'); wid=os.environ.get('FARE_NOTIFIER_ID',socket.gethostname()+'-notifier')
    if not base or not secret or (not os.environ.get('FARE_HMAC_KEY_ID') and os.environ.get('FARE_ALLOW_LEGACY_INGEST_TOKEN')!='1'): raise SystemExit('FARE_RADAR_BASE_URL, FARE_HMAC_KEY_ID and FARE_HMAC_SECRET required')
    deal=os.environ.get('FARE_DEAL_WEBHOOK_URL'); admin=os.environ.get('FARE_ADMIN_WEBHOOK_URL'); once='--once' in sys.argv
    while True:
        run_once(base,secret,wid,deal,admin)
        if once:break
        time.sleep(15)
