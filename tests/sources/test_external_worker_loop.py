import importlib.util,pathlib
ROOT=pathlib.Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('ew',ROOT/'external_worker/worker.py'); ew=importlib.util.module_from_spec(spec); spec.loader.exec_module(ew)
def test_run_once_fetch_ingest_complete(monkeypatch):
    calls=[]
    def post(base,path,payload,secret):
        calls.append((path,payload))
        if path=='/verification-jobs/lease': return {'jobs':[{'job_id':'j1','payload_json':'{"source_id":"s1","url":"https://x.example/deals"}'}]}
        return {'ok':True}
    monkeypatch.setattr(ew,'post_worker_json',post); monkeypatch.setattr(ew,'fetch',lambda url:{'status':200,'url':url,'body':'TPE-KIX 限時特價 NT$3,999','content_sha256':'a'*64,'etag':'"e"','last_modified':None,'content_type':'text/html'})
    out=ew.run_once('https://fare.example','secret','w1'); assert out[0]['status']=='DONE'
    paths=[x[0] for x in calls]; assert paths==['/verification-jobs/lease','/ingest','/verification-jobs/complete']
    ingest=calls[1][1]; assert ingest['structured_payload']['routes']==['TPE-KIX']; assert ingest['content_sha256']=='a'*64
def test_run_once_failure_reports_completion(monkeypatch):
    calls=[]
    def post(base,path,payload,secret):
        calls.append((path,payload)); return {'jobs':[{'job_id':'j1','payload_json':'{"source_id":"s1","url":"https://x.example/deals"}'}]} if path=='/verification-jobs/lease' else {'ok':True}
    monkeypatch.setattr(ew,'post_worker_json',post); monkeypatch.setattr(ew,'fetch',lambda url:(_ for _ in ()).throw(ValueError('MIME_BLOCKED')))
    out=ew.run_once('https://fare.example','secret','w1'); assert out[0]['status']=='FAILED'; assert calls[-1][0]=='/verification-jobs/complete' and calls[-1][1]['success'] is False and calls[-1][1]['schema_drift'] is True
