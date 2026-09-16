import json,pathlib,subprocess
ROOT=pathlib.Path(__file__).resolve().parents[2]
def test_access_review_role_scope_identity_and_readback_chain():
    p=subprocess.run(['node','tests/node_access_review_governance.mjs'],cwd=ROOT,text=True,capture_output=True,check=True)
    x=json.loads(p.stdout)
    assert x['wrong_role']==403
    assert x['source_evidence_write']==202 and x['source_evidence_reviewer']=='global-reviewer'
    assert x['reviewer_mismatch']==400
    assert x['source_apply']==202 and x['source_replay']==202
    assert x['source_read']==200 and x['source_read_reviewer']=='global-reviewer' and x['source_read_valid'] is True
    assert x['source_registry_state']=='SHADOW' and x['source_cross']==403 and x['source_conflict']==409
    assert x['final_gate_forbidden']==403
    assert x['provider_evidence_write']==202 and x['provider_apply']==202 and x['provider_read']==200
    assert x['provider_read_reviewer']=='provider-reviewer' and x['provider_read_valid'] is True
    assert x['provider_registry_budget']==120 and x['provider_cross']==403 and x['invalid_basis']==400
    assert x['wrong_readback_role']==403 and x['legacy_valid'] is False
    assert x['missing_commit_audit']==503 and x['missing_commit_review']==503
    assert x['source_review_rows']==1 and x['provider_review_rows']==1
