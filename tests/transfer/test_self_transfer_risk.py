def test_any_hard_block_prevents_transfer_acceptance(run_cli):
    assert run_cli('self-transfer',{'documentClear':False,'baggageFeasible':True,'scheduledBufferMinutes':300,'requiredBufferMinutes':240}) is False
    assert run_cli('self-transfer',{'documentClear':True,'baggageFeasible':False,'scheduledBufferMinutes':300,'requiredBufferMinutes':240}) is False
    assert run_cli('self-transfer',{'documentClear':True,'baggageFeasible':True,'scheduledBufferMinutes':180,'requiredBufferMinutes':240}) is False


def test_runtime_connection_buffer_profile_and_airport_change_fail_closed():
    import json, pathlib, subprocess
    root=pathlib.Path(__file__).resolve().parents[2]
    p=subprocess.run(['node','tests/node_transfer_runtime.mjs'],cwd=root,text=True,capture_output=True,check=True)
    x=json.loads(p.stdout)
    assert x['short']['required_buffer_minutes']==360 and x['short']['status']=='FAIL'
    assert x['ok']['status']=='PASS' and x['ok']['buffer_confidence']=='LOW'
    assert x['nodoc']['status']=='UNKNOWN' and x['nodoc']['reason']=='DOCUMENT_CLEAR_REQUIRED'
    assert x['noself']['status']=='FAIL' and x['noself']['reason']=='SELF_TRANSFER_PROFILE_DISALLOWED'
    assert x['overnight']['status']=='FAIL' and x['overnight']['reason']=='OVERNIGHT_TRANSFER_PROFILE_DISALLOWED'
    assert x['airportDisallowed']['status']=='FAIL' and x['airportDisallowed']['reason']=='AIRPORT_CHANGE_PROFILE_DISALLOWED'
    assert x['airportOk']['status']=='PASS' and x['airportOk']['required_buffer_minutes']==435
    assert x['airportOk']['airport_change_policy_id']=='icn-gmp-ground'
    assert x['airportMissing']['status']=='UNKNOWN' and x['airportMissing']['reason']=='AIRPORT_CHANGE_ENDPOINTS_REQUIRED'
    assert x['stale']['status']=='UNKNOWN' and x['stale']['reason']=='BUFFER_MODEL_UNCALIBRATED'
    assert x['okFacet']=={'status':'PASS','reason_code':'ALL_TRANSFER_BOUNDARIES_ACCEPTABLE'}
