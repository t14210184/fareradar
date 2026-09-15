import json,pathlib,subprocess
ROOT=pathlib.Path(__file__).resolve().parents[2]
def test_audit_evidence_immutable_and_discovery_edge_dedup():
    p=subprocess.run(['node','tests/node_audit_discovery.mjs'],cwd=ROOT,text=True,capture_output=True,check=True); x=json.loads(p.stdout)
    assert x['a']['idempotent'] is False and x['b']['idempotent'] is True and x['conflict'] is True and x['audit']==1 and x['edge']==1
