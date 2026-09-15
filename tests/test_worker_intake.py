import json, pathlib, subprocess
from tests.fixtures import plan
ROOT=pathlib.Path(__file__).resolve().parents[1]

def test_worker_hmac_candidate_intake(tmp_path):
    f=tmp_path/'plan.json'; f.write_text(json.dumps(plan()))
    p=subprocess.run(['node','tests/node_worker_intake.mjs',str(f)],cwd=ROOT,text=True,capture_output=True,check=True)
    got=json.loads(p.stdout)
    assert got['status']==202 and got['payload']['ok'] is True and got['count']==1
    assert got['bad_status']==401
    assert got['stale_status']==401
