import json,pathlib,subprocess
from tests.fixtures import plan
ROOT=pathlib.Path(__file__).resolve().parents[2]
def test_scoped_candidate_http_invocation_stays_within_d1_50_query_budget(tmp_path):
    f=tmp_path/'base.json';f.write_text(json.dumps(plan()))
    p=subprocess.run(['node','tests/node_candidate_invocation_budget.mjs',str(f)],cwd=ROOT,text=True,capture_output=True,check=True)
    got=json.loads(p.stdout)
    assert got['ok_status']==202 and got['ok_statements']==46 and got['ok_queries']<=50
    assert got['over_status']==400 and got['over_error']=='D1_BATCH_BUDGET_EXCEEDED:47'
    assert got['intakes']==1
