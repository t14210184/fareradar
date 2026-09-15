import datetime as dt,importlib.util,pathlib
ROOT=pathlib.Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('pf',ROOT/'scripts/production_preflight.py'); pf=importlib.util.module_from_spec(spec); spec.loader.exec_module(pf)
def test_only_github_remote_is_accepted():
    assert pf.github_remote_ok('https://github.com/acme/fare-radar.git') is True
    assert pf.github_remote_ok('git@github.com:acme/fare-radar.git') is True
    assert pf.github_remote_ok('file:///tmp/fake.git') is False
    assert pf.github_remote_ok('https://gitlab.com/acme/fare-radar.git') is False
def test_local_env_cannot_fake_provider_readback(monkeypatch):
    monkeypatch.setenv('CLOUDFLARE_API_TOKEN','x'*40); monkeypatch.setenv('CLOUDFLARE_ACCOUNT_ID','y'*32)
    got=pf.evaluate(remote='https://github.com/acme/fare-radar.git')
    assert 'CLOUDFLARE_AUTH_READBACK_MISSING' in got['blockers']
    assert 'PRODUCTION_SECRETS_READBACK_MISSING' in got['blockers']
def test_placeholder_d1_blocks(): assert pf.d1_id() in pf.PLACEHOLDERS
def test_local_gate_evidence_is_bound_to_exact_head(): assert pf.code_ready() is True
def test_legacy_ingest_auth_is_production_blocker(monkeypatch):
    monkeypatch.setenv('ALLOW_LEGACY_INGEST_TOKEN','1')
    got=pf.evaluate(remote='https://github.com/acme/fare-radar.git')
    assert 'LEGACY_INGEST_AUTH_ENABLED' in got['blockers']
def test_provider_evidence_requires_exact_head_freshness_and_secret_manifest(monkeypatch):
    head='a'*40; now=dt.datetime(2026,9,15,4,0,tzinfo=dt.timezone.utc); observed='2026-09-15T03:30:00Z'
    monkeypatch.setattr(pf,'d1_id',lambda:'db-real')
    d1={'provider':'cloudflare','binding_verified':True,'database_id':'db-real','commit_sha':head,'observed_at':observed}
    dep={'provider':'cloudflare','deployed':True,'version_id':'v1','commit_sha':head,'observed_at':observed}
    sec={'provider':'cloudflare','required_secrets_verified':True,'secret_names':['WORKER_TOKEN','INGEST_HMAC_SECRETS'],'legacy_ingest_auth_enabled':False,'commit_sha':head,'observed_at':observed}
    auth={'provider':'cloudflare','auth_verified':True,'observed_at':observed}
    monkeypatch.setattr(pf,'evidence_recent',lambda data,max_hours=24,now=None: True)
    assert pf.d1_readback_ok(d1,head) and pf.deploy_ok(dep,head) and pf.secrets_ok(sec,head) and pf.auth_ok(auth)
    d1['commit_sha']='b'*40; assert not pf.d1_readback_ok(d1,head)
    sec['secret_names']=['INGEST_HMAC_SECRETS']; assert not pf.secrets_ok(sec,head)
    sec['secret_names']=['WORKER_TOKEN','INGEST_HMAC_SECRETS']; sec['legacy_ingest_auth_enabled']=True; assert not pf.secrets_ok(sec,head)
