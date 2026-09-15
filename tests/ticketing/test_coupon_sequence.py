def test_skipped_coupon_always_blocked(run_cli):
    assert run_cli('coupon-sequence',{'allCouponsInSequence':False,'intentionalSkip':True}) is False
    assert run_cli('coupon-sequence',{'allCouponsInSequence':True,'intentionalSkip':False}) is True
