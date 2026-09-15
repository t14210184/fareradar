from __future__ import annotations
import datetime as dt,json,os,pathlib,re,subprocess
ROOT=pathlib.Path(__file__).resolve().parents[1]
PLACEHOLDERS={'','REPLACE_WITH_D1_DATABASE_ID','TODO','TBD'}
REQUIRED_WORKER_SECRETS={'WORKER_TOKEN','INGEST_HMAC_SECRETS'}
def github_remote_ok(url:str|None):
    if not url:return False
    return bool(re.match(r'^(https://github\.com/|git@github\.com:|ssh://git@github\.com/)',url))
def load_json(path:pathlib.Path):
    try:return json.loads(path.read_text())
    except:return None
def git_head():
    try:return subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True,stderr=subprocess.DEVNULL).strip()
    except:return None
def evidence_commit_ok(data,head=None): return bool(data and (data.get('commit_sha')==(head or git_head())))
def evidence_recent(data,max_hours=24,now=None):
    if not data or not data.get('observed_at'):return False
    try:
        seen=dt.datetime.fromisoformat(str(data['observed_at']).replace('Z','+00:00')); now=now or dt.datetime.now(dt.timezone.utc)
        return seen.tzinfo is not None and dt.timedelta(0) <= now-seen <= dt.timedelta(hours=max_hours)
    except:return False
def code_ready(head=None):
    head=head or git_head(); d=load_json(ROOT/'evidence/gate-evidence-latest.json') or {}; s=d.get('summary',{})
    if not head or d.get('commit_sha')!=head:return False
    if not (s.get('LOCAL_TEST_PASS')==37 and s.get('LOCAL_TEST_FAIL')==0 and s.get('EVIDENCE_INCOMPLETE')==0):return False
    return all(g.get('commit_sha')==head and g.get('status')=='LOCAL_TEST_PASS' for g in d.get('gates',[])) and len(d.get('gates',[]))==37
def d1_id():
    txt=(ROOT/'wrangler.jsonc').read_text(); m=re.search(r'"database_id"\s*:\s*"([^"]+)"',txt); return m.group(1) if m else ''
def provider_evidence(name):return load_json(ROOT/'evidence/provider'/f'{name}.json')
def legacy_ingest_enabled():
    if os.environ.get('ALLOW_LEGACY_INGEST_TOKEN')=='1': return True
    try: txt=(ROOT/'wrangler.jsonc').read_text()
    except Exception: return False
    return bool(re.search(r'"ALLOW_LEGACY_INGEST_TOKEN"\s*:\s*"?1"?',txt))
def auth_ok(data): return bool(data and data.get('provider')=='cloudflare' and data.get('auth_verified') is True and evidence_recent(data,24))
def d1_readback_ok(data,head): return bool(data and data.get('provider')=='cloudflare' and data.get('binding_verified') is True and data.get('database_id')==d1_id() and evidence_commit_ok(data,head) and evidence_recent(data,24))
def deploy_ok(data,head): return bool(data and data.get('provider')=='cloudflare' and data.get('deployed') is True and data.get('version_id') and evidence_commit_ok(data,head) and evidence_recent(data,24))
def secrets_ok(data,head):
    names=set(data.get('secret_names') or []) if data else set()
    return bool(data and data.get('provider')=='cloudflare' and data.get('required_secrets_verified') is True and REQUIRED_WORKER_SECRETS<=names and data.get('legacy_ingest_auth_enabled') is False and evidence_commit_ok(data,head) and evidence_recent(data,24))
def shadow_ok(head=None):
    d=load_json(ROOT/'evidence/shadow-acceptance.json') or {}; head=head or git_head()
    return d.get('pass') is True and d.get('commit_sha')==head and d.get('days',0)>=14 and d.get('labeled',0)>=150 and d.get('complex',0)>=30 and d.get('safety_errors',1)==0
def git_remote():
    try:return subprocess.check_output(['git','remote','get-url','origin'],cwd=ROOT,text=True,stderr=subprocess.DEVNULL).strip()
    except:return None
def evaluate(remote=None):
    blockers=[]; head=git_head()
    if not code_ready(head):blockers.append('LOCAL_CODE_GATES_NOT_READY')
    if not github_remote_ok(remote if remote is not None else git_remote()):blockers.append('GITHUB_REMOTE_MISSING')
    if d1_id() in PLACEHOLDERS:blockers.append('D1_DATABASE_ID_MISSING')
    if legacy_ingest_enabled():blockers.append('LEGACY_INGEST_AUTH_ENABLED')
    auth=provider_evidence('cloudflare-auth') or {}; d1=provider_evidence('d1-readback') or {}; deploy=provider_evidence('worker-deploy') or {}; secrets=provider_evidence('production-secrets') or {}
    if not auth_ok(auth):blockers.append('CLOUDFLARE_AUTH_READBACK_MISSING')
    if not d1_readback_ok(d1,head):blockers.append('D1_PROVIDER_READBACK_MISSING')
    if not deploy_ok(deploy,head):blockers.append('WORKER_DEPLOY_READBACK_MISSING')
    if not secrets_ok(secrets,head):blockers.append('PRODUCTION_SECRETS_READBACK_MISSING')
    if not shadow_ok(head):blockers.append('SHADOW_ACCEPTANCE_MISSING')
    return {'code_ready':code_ready(head),'production_ready':not blockers,'commit_sha':head,'blockers':blockers}
if __name__=='__main__': print(json.dumps(evaluate(),ensure_ascii=False,indent=2))
