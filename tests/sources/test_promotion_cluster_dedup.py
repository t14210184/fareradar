def test_same_promotion_fingerprint_across_channels(run_cli):
    a={'market':'TW','airline':'IT','routes':['TPE-KIX','KHH-KIX'],'sale_start':'2026-09-16','travel_start':'2026-10-01','promo_code':'SALE'}
    b=dict(a); b['routes']=['KHH-KIX','TPE-KIX']
    assert run_cli('promo-fingerprint',a)==run_cli('promo-fingerprint',b)
