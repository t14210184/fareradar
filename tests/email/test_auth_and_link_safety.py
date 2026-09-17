def test_email_auth_and_link_safety(run_cli):
    assert run_cli('email-trust',{'dkim':'PASS','spf':'PASS','dmarc':'PASS','links':['https://airline.example/deal']})=='TRUSTED'
    assert run_cli('email-trust',{'dkim':'FAIL','spf':'PASS','dmarc':'PASS','links':['https://airline.example/deal']})=='UNTRUSTED'
    assert run_cli('email-trust',{'dkim':'PASS','spf':'PASS','dmarc':'PASS','links':['http://evil.example']})=='UNTRUSTED'
