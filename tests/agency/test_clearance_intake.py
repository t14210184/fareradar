def test_anonymous_payment_never_seller_confirmed(run_cli):
    assert run_cli('clearance-state',{'seller_verified':True,'official_readback':True,'anonymous_payment':True})!='SELLER_CONFIRMED'
    assert run_cli('clearance-state',{'seller_verified':True,'official_readback':True,'anonymous_payment':False})=='SELLER_CONFIRMED'
