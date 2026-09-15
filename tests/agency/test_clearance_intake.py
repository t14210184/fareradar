def test_anonymous_payment_never_seller_confirmed(run_cli):
    assert run_cli('clearance-state',{'seller_verified':True,'official_readback':True,'anonymous_payment':True})!='SELLER_CONFIRMED'
    assert run_cli('clearance-state',{'seller_verified':True,'official_readback':True,'anonymous_payment':False})=='SELLER_CONFIRMED'

def test_agency_seller_recheck_is_partner_and_lease_scoped():
    import json, pathlib, subprocess
    root=pathlib.Path(__file__).resolve().parents[2]
    p=subprocess.run(['node','tests/node_agency_recheck.mjs'],cwd=root,text=True,capture_output=True,check=True)
    x=json.loads(p.stdout)
    assert x['none']==0 and x['leased']==1
    assert x['wrongWorker']=='AGENCY_RECHECK_LIVE_LEASE_REQUIRED'
    assert x['ok']['result']=='SELLER_CONFIRMED' and x['ok']['state']=='DONE'
    assert x['idem']['idempotent'] is True and x['intents']==1
    assert x['row']=={'seller_verification_state':'VERIFIED_READBACK','price':6888.0,'seats_available':1,'state':'SELLER_CONFIRMED'}
    assert x['q']['state']=='DONE'
    assert x['ev']=={'result_state':'SELLER_CONFIRMED','readback_basis':'PARTNER_API'}
    assert x['payload']['kind']=='P0-PROVISIONAL' and x['payload']['verification_state']=='SELLER_CONFIRMED'
    assert x['payload']['actionable'] is False and x['payload']['bookable'] is False
