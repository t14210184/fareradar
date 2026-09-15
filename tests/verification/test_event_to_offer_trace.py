def test_claims_without_live_or_seller_readback_never_confirm(run_cli):
    ev=[{'kind':'PROMOTION','authority':'HIGH_FOR_OWN_TERMS'},{'kind':'SOCIAL','authority':'LOW'},{'kind':'CACHED_FARE','authority':'INDICATIVE'}]
    assert run_cli('can-confirm',ev) is False
    assert run_cli('can-confirm',ev+[{'kind':'LIVE_OFFER','authority':'BOOKABLE'}]) is True
