import json,pathlib,subprocess
ROOT=pathlib.Path(__file__).resolve().parents[2]
def test_partner_and_email_runtime_minimal_storage():
    p=subprocess.run(['node','tests/node_partner_email.mjs'],cwd=ROOT,text=True,capture_output=True,check=True); x=json.loads(p.stdout)
    assert x['ar']['state']=='AGENCY_CLAIMED' and x['agency']=={'state':'AGENCY_CLAIMED','seats_available':1}
    assert x['er']['trust_class']=='TRUSTED' and x['forged']['trust_class']=='UNTRUSTED'
    assert x['rawBlocked'] is True and x['raw_column_exists']==0
    assert x['email_count']==2 and x['obs_count']==3 and x['outbox_count']==3
    assert x['projected']=={'claimed':3,'done':3}
    assert x['projectedAgain']=={'claimed':0,'done':0}
    assert x['domain_done']==3
    assert x['promotion_count']==1 and x['promotion_state']=='DISCOVERED'
    assert x['promotion_evidence']=='obs-e1'
