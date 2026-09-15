import json, pathlib, subprocess
from tests.fixtures import plan
ROOT=pathlib.Path(__file__).resolve().parents[1]

def test_atomic_candidate_intake_idempotent(tmp_path):
    f=tmp_path/'plan.json'; f.write_text(json.dumps(plan()))
    p=subprocess.run(['node','tests/node_candidate_intake.mjs',str(f)],cwd=ROOT,text=True,capture_output=True,check=True)
    got=json.loads(p.stdout)
    assert got['r1']['statements'] <= 46
    assert got['counts']=={'itinerary_candidates':1,'candidate_plan_intakes':1,'ticket_components':2,'transfer_boundaries':1,'cost_components':2,'readiness_facets':7,'document_requirements':1,'four_leg_liabilities':0}
    assert got['conflict'] is True
    assert got['missingRefBlocked'] is True
