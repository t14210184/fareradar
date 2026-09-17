import json,pathlib,subprocess
ROOT=pathlib.Path(__file__).resolve().parents[2]
def test_durable_shadow_corpus_canonical_review_runtime_days_and_acceptance():
    p=subprocess.run(['node','tests/node_shadow_corpus_runtime.mjs'],cwd=ROOT,text=True,capture_output=True,check=True)
    x=json.loads(p.stdout)
    assert x['wrong_role']==403 and x['missing_commit']==503 and x['production_write']==409
    assert x['complex_mismatch']==400 and x['observed_mismatch']==400 and x['canonical_mismatch']==400
    assert x['itinerary_write']==202 and x['itinerary_replay']==202
    assert x['read_reviewer']=='shadow-reviewer' and x['read_commit']=='d'*40
    assert x['changed_same_sample']==409 and x['duplicate_unit']==409
    assert [x['promo'],x['agency'],x['source'],x['email'],x['route']]==[202,202,202,202,202]
    assert x['runtime_days_after_scheduler']==1 and x['initial_pass'] is False
    assert x['full_pass'] is True and x['full_days']>=14 and x['full_candidates']>=150 and x['full_complex']>=30
    assert x['full_source']>=30 and x['full_agency']>=10
    assert x['coverage']==['S09','S11','S12','S14','S15']
    assert x['missing']==0 and x['production_pass'] is False
