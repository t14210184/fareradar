from __future__ import annotations
import json,os,pathlib,re,subprocess
ROOT=pathlib.Path(__file__).resolve().parents[1]
PLACEHOLDERS={'','REPLACE_WITH_D1_DATABASE_ID','TODO','TBD'}
def github_remote_ok(url:str|None):
    if not url:return False
    return bool(re.match(r'^(https://github\.com/|git@github\.com:|ssh://git@github\.com/)',url))
def load_json(path:pathlib.Path):
    try:return json.loads(path.read_text())
    except:return None
def code_ready():
    d=load_json(ROOT/'evidence/gate-evidence-latest.json') or {}; s=d.get('summary',{})
    return s.get('LOCAL_TEST_PASS')==37 and s.get('LOCAL_TEST_FAIL')==0 and s.get('EVIDENCE_INCOMPLETE')==0
def d1_id():
    txt=(ROOT/'wrangler.jsonc').read_text(); m=re.search(r'"database_id"\s*:\s*"([^"]+)"',txt); return m.group(1) if m else ''
def provider_evidence(name):return load_json(ROOT/'evidence/provider'/f'{name}.json')
def legacy_ingest_enabled():
    if os.environ.get('ALLOW_LEGACY_INGEST_TOKEN')=='1': return True
    try: txt=(ROOT/'wrangler.jsonc').read_text()
    except Exception: return False
    return bool(re.search(r'"ALLOW_LEGACY_INGEST_TOKEN"\s*:\s*"?1"?',txt))
def shadow_ok():
    d=load_json(ROOT/'evidence/shadow-acceptance.json') or {}
    return d.get('pass') is True and d.get('days',0)>=14 and d.get('labeled',0)>=150 and d.get('complex',0)>=30 and d.get('safety_errors',1)==0
def git_remote():
    try:return subprocess.check_output(['git','remote','get-url','origin'],cwd=ROOT,text=True,stderr=subprocess.DEVNULL).strip()
    except:return None
def evaluate(remote=None):
    blockers=[]
    if not code_ready():blockers.append('LOCAL_CODE_GATES_NOT_READY')
    if not github_remote_ok(remote if remote is not None else git_remote()):blockers.append('GITHUB_REMOTE_MISSING')
    if d1_id() in PLACEHOLDERS:blockers.append('D1_DATABASE_ID_MISSING')
    if legacy_ingest_enabled():blockers.append('LEGACY_INGEST_AUTH_ENABLED')
    auth=provider_evidence('cloudflare-auth') or {}; d1=provider_evidence('d1-readback') or {}; deploy=provider_evidence('worker-deploy') or {}; secrets=provider_evidence('production-secrets') or {}
    if auth.get('provider')!='cloudflare' or auth.get('auth_verified') is not True:blockers.append('CLOUDFLARE_AUTH_READBACK_MISSING')
    if d1.get('provider')!='cloudflare' or d1.get('binding_verified') is not True:blockers.append('D1_PROVIDER_READBACK_MISSING')
    if deploy.get('provider')!='cloudflare' or deploy.get('deployed') is not True or not deploy.get('version_id'):blockers.append('WORKER_DEPLOY_READBACK_MISSING')
    if secrets.get('provider')!='cloudflare' or secrets.get('required_secrets_verified') is not True:blockers.append('PRODUCTION_SECRETS_READBACK_MISSING')
    if not shadow_ok():blockers.append('SHADOW_ACCEPTANCE_MISSING')
    return {'code_ready':code_ready(),'production_ready':not blockers,'blockers':blockers}
if __name__=='__main__': print(json.dumps(evaluate(),ensure_ascii=False,indent=2))
