def test_any_hard_block_prevents_transfer_acceptance(run_cli):
    assert run_cli('self-transfer',{'documentClear':False,'baggageFeasible':True,'scheduledBufferMinutes':300,'requiredBufferMinutes':240}) is False
    assert run_cli('self-transfer',{'documentClear':True,'baggageFeasible':False,'scheduledBufferMinutes':300,'requiredBufferMinutes':240}) is False
    assert run_cli('self-transfer',{'documentClear':True,'baggageFeasible':True,'scheduledBufferMinutes':180,'requiredBufferMinutes':240}) is False

def test_runtime_connection_buffer_components_and_fail_closed():
    import json, pathlib, subprocess
    root=pathlib.Path(__file__).resolve().parents[2]
    p=subprocess.run(['node','tests/node_transfer_runtime.mjs'],cwd=root,text=True,capture_output=True,check=True)
    x=json.loads(p.stdout)
    assert x['short']['required_buffer_minutes']==360 and x['short']['status']=='FAIL'
    assert x['ok']['status']=='PASS' and x['ok']['buffer_confidence']=='LOW'
    assert x['nodoc']['status']=='UNKNOWN' and x['nodoc']['reason']=='DOCUMENT_CLEAR_REQUIRED'
    assert x['airport']['status']=='FAIL' and x['airport']['reason']=='AIRPORT_CHANGE_REQUIRES_EXPLICIT_MODEL'
    assert x['stale']['status']=='UNKNOWN' and x['stale']['reason']=='BUFFER_MODEL_UNCALIBRATED'
    assert x['okFacet']=={'status':'PASS','reason_code':'ALL_TRANSFER_BOUNDARIES_ACCEPTABLE'}
