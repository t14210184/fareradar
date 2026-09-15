def test_any_hard_block_prevents_transfer_acceptance(run_cli):
    assert run_cli('self-transfer',{'documentClear':False,'baggageFeasible':True,'scheduledBufferMinutes':300,'requiredBufferMinutes':240}) is False
    assert run_cli('self-transfer',{'documentClear':True,'baggageFeasible':False,'scheduledBufferMinutes':300,'requiredBufferMinutes':240}) is False
    assert run_cli('self-transfer',{'documentClear':True,'baggageFeasible':True,'scheduledBufferMinutes':180,'requiredBufferMinutes':240}) is False
