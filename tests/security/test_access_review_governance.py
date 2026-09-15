import json,pathlib,subprocess
ROOT=pathlib.Path(__file__).resolve().parents[2]
def test_access_reviews_are_human_scoped_immutable_and_same_source_readable():
    p=subprocess.run(['node','tests/node_access_review_governance.mjs'],cwd=ROOT,text=True,capture_output=True,check=True)
    got=json.loads(p.stdout)
    assert got['absent']==200 and got['absent_is_null'] is True
    assert got['source_evidence']==202 and got['source_evidence_read']==200 and got['source_evidence_hash']==got['sourceHash']
    assert got['source_write']==202 and got['source_replay']==202 and got['source_replay_idem'] is True
    assert got['source_read']==200 and got['source_reviewer']=='access-global' and got['source_hash']==got['sourceHash']
    assert got['source_registry']['lifecycle_state']=='SHADOW' and got['source_registry']['access_basis']=='PUBLIC_OFFICIAL_PAGE'
    assert got['audit_conflict']==409 and got['source_conflict']==409 and got['source_scoped_read_cross']==403
    assert got['provider_evidence']==202 and got['provider_write']==202 and got['provider_read']==200
    assert got['provider_reviewer']=='access-global' and got['provider_hash']==got['providerHash']
    assert got['provider_registry']['access_basis']=='OFFICIAL_API' and got['provider_registry']['rate_policy']=='TARGETED_ONLY'
    assert got['provider_conflict']==409
    assert got['final_pg']==403
    assert got['source_scoped_cross']==403 and got['provider_scoped_cross']==403
    assert got['generic_source']==403 and got['unsupported']==400 and got['no_commit']==503
    assert got['legacy_reviewer'] is None
