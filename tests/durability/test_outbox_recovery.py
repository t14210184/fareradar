import json,pathlib,subprocess
ROOT=pathlib.Path(__file__).resolve().parents[2]
def test_notification_and_domain_outbox_recovery():
    p=subprocess.run(['node','tests/node_outbox.mjs'],cwd=ROOT,text=True,capture_output=True,check=True); x=json.loads(p.stdout)
    assert x['jobs']==1 and x['reclaimed']==1 and x['wrongNotificationAck'] is True and x['retry']=='RETRY' and x['dead']=='DEAD'
    assert x['admin']>=1 and x['counts']['notifications']==2
    assert x['ev']==1 and x['ev2']==1 and x['wrongDomainAck'] is True and x['dstate']=='DONE' and x['dreplay']=='DONE' and x['counts']['domain_done']==1
