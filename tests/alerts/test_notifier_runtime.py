import importlib.util,pathlib
ROOT=pathlib.Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('notifier',ROOT/'notification_worker/notifier.py'); n=importlib.util.module_from_spec(spec); spec.loader.exec_module(n)
def test_deal_admin_strict_routing_and_idempotency(monkeypatch):
    calls=[]; sent=[]
    def post(base,path,payload,secret):
        calls.append((path,payload))
        if path=='/notifications/lease': return {'jobs':[{'notification_id':'d1','channel_class':'DEAL','payload_json':'{"x":1}','attempts':1},{'notification_id':'a1','channel_class':'ADMIN','payload_json':'{"x":2}','attempts':2}]}
        return {'state':'DELIVERED'}
    def send(url,payload,nid,attempt): sent.append((url,nid,attempt)); return {'ok':True,'retryable':False,'status':200}
    monkeypatch.setattr(n,'post_json',post); monkeypatch.setattr(n,'send_webhook',send)
    out=n.run_once('https://fare.example','s','w','https://deal.example/h','https://admin.example/h')
    assert sent==[('https://deal.example/h','d1',1),('https://admin.example/h','a1',2)]
    assert [x[0] for x in calls].count('/notifications/ack')==2 and all(x['ok'] for x in out)
def test_admin_never_falls_back_to_deal(monkeypatch):
    calls=[]; sent=[]
    def post(base,path,payload,secret):
        calls.append((path,payload)); return {'jobs':[{'notification_id':'a1','channel_class':'ADMIN','payload_json':'{}','attempts':1}]} if path=='/notifications/lease' else {'state':'DEAD'}
    monkeypatch.setattr(n,'post_json',post); monkeypatch.setattr(n,'send_webhook',lambda *a,**k: sent.append(a))
    out=n.run_once('https://fare.example','s','w','https://deal.example/h',None)
    assert sent==[] and out[0]['error']=='CHANNEL_NOT_CONFIGURED'; assert calls[-1][1]['retryable'] is False
def test_retryable_http_is_acked_retryable(monkeypatch):
    calls=[]
    def post(base,path,payload,secret): calls.append((path,payload)); return {'jobs':[{'notification_id':'d1','channel_class':'DEAL','payload_json':'{}','attempts':1}]} if path=='/notifications/lease' else {}
    monkeypatch.setattr(n,'post_json',post); monkeypatch.setattr(n,'send_webhook',lambda *a,**k:{'ok':False,'retryable':True,'status':503})
    n.run_once('https://fare.example','s','w','https://deal.example/h','https://admin.example/h'); assert calls[-1][1]['retryable'] is True and calls[-1][1]['error']=='HTTP_503'
