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
    assert 'GITHUB_PROVIDER_READBACK_MISSING' in got['blockers']
    assert 'CLOUDFLARE_AUTH_READBACK_MISSING' in got['blockers']
    assert 'PRODUCTION_SECRETS_READBACK_MISSING' in got['blockers']
def test_placeholder_d1_blocks(): assert pf.d1_id() in pf.PLACEHOLDERS
def test_local_gate_evidence_validator_is_bound_to_exact_context(monkeypatch):
    head='a'*40
    ctx={'commit_sha':head,'spec_sha256':'b'*64,'dependency_lock_sha256':'c'*64,'test_corpus_sha256':'d'*64}
    monkeypatch.setattr(pf,'_current_evidence_context',lambda h:ctx)
    mapping=pf._spec_gate_mapping(); assert len(mapping)==37
    gates=[{'gate_id':gid,'exact_command':cmd,'expected_threshold':threshold,'status':'LOCAL_TEST_PASS','commit_sha':head,'report_sha256':'e'*64} for gid,cmd,threshold in mapping]
    evidence={'schema_version':2,**ctx,'summary':{'LOCAL_TEST_PASS':37,'LOCAL_TEST_FAIL':0,'EVIDENCE_INCOMPLETE':0},'gates':gates,'full_suite':{'status':'FULL_SUITE_PASS','stage_count':5,'file_count':100,'report_sha256':'f'*64}}
    assert pf.code_ready_from_evidence(evidence,head) is True
    evidence['test_corpus_sha256']='0'*64; assert pf.code_ready_from_evidence(evidence,head) is False
def test_legacy_ingest_auth_is_production_blocker(monkeypatch):
    monkeypatch.setenv('ALLOW_LEGACY_INGEST_TOKEN','1')
    got=pf.evaluate(remote='https://github.com/acme/fare-radar.git')
    assert 'LEGACY_INGEST_AUTH_ENABLED' in got['blockers']
def test_github_provider_evidence_requires_exact_head_ci_and_protection(monkeypatch):
    head='a'*40
    monkeypatch.setattr(pf,'evidence_recent',lambda data,max_hours=24,now=None: True)
    good={'provider':'github','repository_full_name':'acme/fare-radar','visibility':'public','default_branch':'main','commit_sha':head,'ci_conclusion':'success','branch_protection_verified':True,'required_status_contexts':['test']}
    monkeypatch.setenv('FARE_GITHUB_REPOSITORY','acme/fare-radar')
    assert pf.github_readback_ok(good,head)
    bad=dict(good,commit_sha='b'*40); assert not pf.github_readback_ok(bad,head)
    bad=dict(good,required_status_contexts=['lint']); assert not pf.github_readback_ok(bad,head)
    bad=dict(good,repository_full_name='other/fare-radar'); assert not pf.github_readback_ok(bad,head)
def test_provider_evidence_requires_exact_head_freshness_and_secret_manifest(monkeypatch):
    head='a'*40; observed='2026-09-15T03:30:00Z'; session='session-1'
    monkeypatch.setattr(pf,'d1_id',lambda:'db-real')
    d1={'provider':'cloudflare','readback_session_id':session,'binding_verified':True,'migrations_verified':True,'baseline_seeds_verified':True,'dispatchable_reviews_verified':True,'database_id':'db-real','commit_sha':head,'observed_at':observed}
    dep={'provider':'cloudflare','readback_session_id':session,'deployed':True,'version_id':'v1','deployment_mode':'SHADOW_ACCEPTANCE','commit_sha':head,'observed_at':observed}
    sec={'provider':'cloudflare','readback_session_id':session,'required_secrets_verified':True,'secret_names':['WORKER_TOKEN','INGEST_HMAC_SECRETS'],'legacy_ingest_auth_enabled':False,'commit_sha':head,'observed_at':observed}
    auth={'provider':'cloudflare','readback_session_id':session,'auth_verified':True,'observed_at':observed}
    monkeypatch.setattr(pf,'evidence_recent',lambda data,max_hours=24,now=None: True)
    assert pf.cloudflare_session_ok(auth,d1,dep,sec)
    assert pf.d1_readback_ok(d1,head) and pf.deploy_ok(dep,head) and pf.secrets_ok(sec,head) and pf.auth_ok(auth)
    d1['commit_sha']='b'*40; assert not pf.d1_readback_ok(d1,head)
    d1['commit_sha']=head; d1['migrations_verified']=False; assert not pf.d1_readback_ok(d1,head)
    sec['secret_names']=['INGEST_HMAC_SECRETS']; assert not pf.secrets_ok(sec,head)
    sec['secret_names']=['WORKER_TOKEN','INGEST_HMAC_SECRETS']; sec['legacy_ingest_auth_enabled']=True; assert not pf.secrets_ok(sec,head)
def test_cloudflare_provider_evidence_cannot_be_spliced_across_sessions():
    a={'readback_session_id':'one'}; b={'readback_session_id':'one'}; c={'readback_session_id':'one'}; d={'readback_session_id':'one'}
    assert pf.cloudflare_session_ok(a,b,c,d)
    d['readback_session_id']='two'
    assert not pf.cloudflare_session_ok(a,b,c,d)
    assert not pf.cloudflare_session_ok({},b,c,d)
