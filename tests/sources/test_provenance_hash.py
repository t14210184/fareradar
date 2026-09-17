def test_provenance_requires_https_sha_time(run_cli):
    good={'source_id':'s','canonical_url':'https://x.example/a','observed_at':'2026-09-15T00:00:00Z','content_sha256':'a'*64,'parser_version':'1','access_basis':'PUBLIC_OFFICIAL_PAGE'}
    assert run_cli('provenance-valid',good) is True
    bad=dict(good); bad['content_sha256']='abc'; assert run_cli('provenance-valid',bad) is False
