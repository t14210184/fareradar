def test_skipped_coupon_always_blocked(run_cli):
    assert run_cli('coupon-sequence',{'allCouponsInSequence':False,'intentionalSkip':True}) is False
    assert run_cli('coupon-sequence',{'allCouponsInSequence':True,'intentionalSkip':False}) is True

def test_ticketing_policy_runtime_blocks_skip_and_guards_back_to_back():
    import json, pathlib, subprocess
    root=pathlib.Path(__file__).resolve().parents[2]
    p=subprocess.run(['node','tests/node_ticketing_guard.mjs'],cwd=root,text=True,capture_output=True,check=True)
    x=json.loads(p.stdout)
    assert x['missingPolicy']['coupon_status']=='FAIL' and x['missingPolicy']['coupon_reason']=='UNKNOWN_POLICY_CONSEQUENCE'
    assert x['withPolicy']['coupon_status']=='FAIL' and x['withPolicy']['coupon_reason']=='COUPON_RECALCULATION_LIABILITY'
    assert x['nestedUnknown']['back_to_back_detected'] is True and x['nestedUnknown']['back_to_back_reason']=='BACK_TO_BACK_POLICY_UNKNOWN'
    assert x['nestedAllowed']['back_to_back_detected'] is True and x['nestedAllowed']['back_to_back_reason']=='NO_BACK_TO_BACK_PATTERN'
    assert x['nestedState']['verification_state']=='PROBABLE'
