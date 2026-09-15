from tests.fixtures import plan
import json, pathlib, subprocess
ROOT=pathlib.Path(__file__).resolve().parents[2]
def test_candidate_intake_batch_under_50(tmp_path):
    f=tmp_path/'p.json'; f.write_text(json.dumps(plan()))
    p=subprocess.run(['node','tests/node_candidate_intake.mjs',str(f)],cwd=ROOT,text=True,capture_output=True,check=True)
    got=json.loads(p.stdout); assert got['r1']['statements'] <= 46
