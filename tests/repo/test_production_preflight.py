import importlib.util,pathlib
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
def test_local_gate_evidence_can_be_ready(): assert pf.code_ready() is True
def test_legacy_ingest_auth_is_production_blocker(monkeypatch):
    monkeypatch.setenv('ALLOW_LEGACY_INGEST_TOKEN','1')
    got=pf.evaluate(remote='https://github.com/acme/fare-radar.git')
    assert 'LEGACY_INGEST_AUTH_ENABLED' in got['blockers']
