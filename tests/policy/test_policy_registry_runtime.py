import json, subprocess, pathlib
ROOT=pathlib.Path(__file__).resolve().parents[2]
def run():
    p=subprocess.run(['node','tests/node_policy_registry.mjs'],cwd=ROOT,text=True,capture_output=True,check=True)
    return json.loads(p.stdout.strip().splitlines()[-1])
def test_fresh_event_time_policy_can_clear_document_facet():
    r=run(); assert r['clear']['document_status']=='PASS'; assert r['clear']['policy_status']=='PASS'
    f={x['facet_type']:x for x in r['clearFacets']}; assert f['DOCUMENT_CLEAR']['status']=='PASS'; assert f['POLICY_FRESH']['status']=='PASS'
    assert r['doc']['jurisdiction']=='JP'; assert r['doc']['valid_for_event_at']=='2026-11-02T03:30:00Z'; assert r['doc']['source_snapshot_id']=='jp-entry-v1'
def test_stale_policy_revokes_readiness_instead_of_reusing_old_clearance():
    r=run(); assert r['stale']['policy_status']=='STALE'; assert r['stale']['document_status']=='UNKNOWN'
    f={x['facet_type']:x for x in r['staleFacets']}; assert f['POLICY_FRESH']['status']=='STALE'; assert f['DOCUMENT_CLEAR']['status']=='UNKNOWN'
def test_policy_snapshot_is_immutable_by_record_id():
    assert run()['conflict']=='POLICY_RECORD_IMMUTABLE_CONFLICT'
