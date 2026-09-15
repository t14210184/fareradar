import importlib.util,pathlib,socket,pytest
ROOT=pathlib.Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('ew',ROOT/'external_worker/worker.py'); ew=importlib.util.module_from_spec(spec); spec.loader.exec_module(ew)
def test_public_ip_policy():
    assert ew._public_ip('8.8.8.8') is True
    for ip in ['127.0.0.1','10.0.0.1','169.254.1.1','::1']: assert ew._public_ip(ip) is False
def test_https_and_dns_ssrf_gate(monkeypatch):
    monkeypatch.setattr(ew.socket,'getaddrinfo',lambda *a,**k:[(socket.AF_INET,socket.SOCK_STREAM,6,'',('8.8.8.8',443))]); assert ew.validate_url('https://example.com/a') is True
    with pytest.raises(ValueError,match='HTTPS_REQUIRED'): ew.validate_url('http://example.com')
    monkeypatch.setattr(ew.socket,'getaddrinfo',lambda *a,**k:[(socket.AF_INET,socket.SOCK_STREAM,6,'',('127.0.0.1',443))]);
    with pytest.raises(ValueError,match='SSRF_BLOCKED'): ew.validate_url('https://example.com/a')
def test_structured_signal_is_discovery_only():
    x=ew.structured_signal('TPE-KIX 限時特價 NT$3,999 優惠碼 SALE','s1'); assert x['extraction_type']=='PROMOTION_SIGNAL'; assert x['structured_payload']['routes']==['TPE-KIX']; assert x['structured_payload']['prices'][0]['amount']==3999
