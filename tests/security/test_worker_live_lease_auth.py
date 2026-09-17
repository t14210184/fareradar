import json,pathlib,subprocess
ROOT=pathlib.Path(__file__).resolve().parents[2]
def test_external_worker_token_is_bounded_by_live_source_lease():
    p=subprocess.run(['node','tests/node_worker_lease_auth.mjs'],cwd=ROOT,text=True,capture_output=True,check=True)
    got=json.loads(p.stdout)
    assert got['unauthorized']==401 and got['leased']==1
    assert got['wrong_worker']==403 and got['wrong_source']==403
    assert got['good']==202 and got['observations']==1
    assert got['wrong_complete']==403 and got['complete']==200 and got['job_state']=='DONE'
    assert got['after_done']==403
