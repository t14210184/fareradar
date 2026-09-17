import json,pathlib,subprocess
ROOT=pathlib.Path(__file__).resolve().parents[2]
def test_verification_job_retry_then_dead_admin():
    p=subprocess.run(['node','tests/node_verification_retry.mjs'],cwd=ROOT,text=True,capture_output=True,check=True); x=json.loads(p.stdout)
    assert x['retry']=='RETRY' and x['r1']['state']=='PENDING' and x['r1']['last_error']=='HTTP_500'
    assert x['dead']=='DEAD' and x['r2']['state']=='DEAD' and x['admin']==1
