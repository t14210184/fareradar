import json,pathlib,subprocess
ROOT=pathlib.Path(__file__).resolve().parents[2]
def test_provider_external_writes_require_matching_live_job_lease():
    p=subprocess.run(['node','tests/node_provider_live_lease_auth.mjs'],cwd=ROOT,text=True,capture_output=True,check=True)
    got=json.loads(p.stdout)
    assert got['ok']==202 and got['offers']==1
    assert got['wrong_worker']==403 and got['wrong_job']==403
    assert got['done']==200 and got['replay']==200 and got['state']=='DONE'
    assert got['after_done']==403
