import json, pathlib, subprocess
from tests.fixtures import plan
ROOT=pathlib.Path(__file__).resolve().parents[2]

def test_confirmed_candidate_feedback_counts_each_source_once_and_earliest_wins(tmp_path):
    f=tmp_path/'plan.json'; f.write_text(json.dumps(plan()))
    p=subprocess.run(['node','tests/node_source_outcome_attribution.mjs',str(f)],cwd=ROOT,text=True,capture_output=True,check=True)
    x=json.loads(p.stdout)
    assert x['first']['done']==1 and x['second']['claimed']==0
    assert x['attrs']==[
        {'source_id':'peach_tw_official','observation_id':'obs-peach','first_win':0},
        {'source_id':'tigerair_tw_official','observation_id':'obs-tiger','first_win':1},
    ]
    assert x['health']==[
        {'source_id':'peach_tw_official','confirmed_count':1,'first_win_count':0},
        {'source_id':'tigerair_tw_official','confirmed_count':1,'first_win_count':1},
    ]
