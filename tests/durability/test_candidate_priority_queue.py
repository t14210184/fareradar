import json, pathlib, subprocess
ROOT=pathlib.Path(__file__).resolve().parents[2]

def test_candidate_priority_queue_idempotent_lease_retry():
    p=subprocess.run(['node','tests/node_candidate_priority.mjs'],cwd=ROOT,text=True,capture_output=True,check=True)
    x=json.loads(p.stdout)
    assert x['count']==1 and x['score']==80
    assert x['first']==1 and x['retry']=='RETRY'
    assert x['tooEarly']==0 and x['later']==1 and x['wrongAck'] is True
    assert x['done']=='DONE' and x['state']=='DONE'
