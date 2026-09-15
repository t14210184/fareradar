import json, pathlib, subprocess
ROOT=pathlib.Path(__file__).resolve().parents[2]

def test_provider_runtime_readback_and_candidate_lease_are_fail_closed():
    p=subprocess.run(['node','tests/node_provider_runtime.mjs'],cwd=ROOT,text=True,capture_output=True,check=True)
    x=json.loads(p.stdout)
    assert x['before']=={'ready':False,'reason':'PROVIDER_ACCESS_NOT_READY'}
    assert x['ready']=={'ready':True,'reason':'READY'}
    assert x['seller']=={'ready':False,'reason':'CAPABILITY_NOT_ALLOWED'}
    assert x['leased']==[{'signal_type':'PROMOTION','required_verification':'LIVE_REPRICE'}]
    assert x['pendingAgency']==1
    assert x['expired']=={'ready':False,'reason':'RUNTIME_READBACK_MISSING'}
