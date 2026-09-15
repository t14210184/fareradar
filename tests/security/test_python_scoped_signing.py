import hashlib,hmac,importlib.util,pathlib
ROOT=pathlib.Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('ew_auth',ROOT/'external_worker/worker.py'); ew=importlib.util.module_from_spec(spec); spec.loader.exec_module(ew)
def test_python_signer_binds_method_path_body_and_nonce(monkeypatch):
    monkeypatch.setenv('FARE_HMAC_KEY_ID','worker-key')
    body='{"x":1}'; secret='worker-secret-0123456789'; nonce='nonce-python-abcdefghijkl'; ts='1770000000000'
    h=ew.sign_headers(secret,body,'/ingest','POST',nonce=nonce,ts=ts)
    bh=hashlib.sha256(body.encode()).hexdigest(); canonical='\n'.join(['worker-key',ts,nonce,'POST','/ingest',bh])
    assert h['x-fare-signature']==hmac.new(secret.encode(),canonical.encode(),hashlib.sha256).hexdigest()
    assert h['x-fare-key-id']=='worker-key' and h['x-fare-nonce']==nonce
def test_python_signer_requires_scoped_key_unless_explicit_legacy(monkeypatch):
    monkeypatch.delenv('FARE_HMAC_KEY_ID',raising=False); monkeypatch.delenv('FARE_ALLOW_LEGACY_INGEST_TOKEN',raising=False)
    try: ew.sign_headers('secret-0123456789','{}','/ingest')
    except ValueError as e: assert str(e)=='FARE_HMAC_KEY_ID_REQUIRED'
    else: raise AssertionError('expected scoped key requirement')
