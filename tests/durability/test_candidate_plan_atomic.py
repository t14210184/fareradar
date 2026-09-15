import json, pathlib, subprocess
from tests.fixtures import plan
ROOT=pathlib.Path(__file__).resolve().parents[2]
def test_duplicate_candidate_intake_idempotent(tmp_path):
    f=tmp_path/'p.json'; f.write_text(json.dumps(plan()))
    p=subprocess.run(['node','tests/node_candidate_intake.mjs',str(f)],cwd=ROOT,text=True,capture_output=True,check=True)
    got=json.loads(p.stdout); assert got['counts']['candidate_plan_intakes']==1; assert got['conflict'] is True
