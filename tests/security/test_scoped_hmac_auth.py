import json,pathlib,subprocess
ROOT=pathlib.Path(__file__).resolve().parents[2]
def test_scoped_hmac_nonce_path_body_and_identity_guards():
    p=subprocess.run(['node','tests/node_scoped_auth.mjs'],cwd=ROOT,text=True,capture_output=True,check=True)
    got=json.loads(p.stdout)
    assert got['ok']==202 and got['audits']==1
    assert got['replay']==401 and got['wrong_body']==401 and got['wrong_path']==401
    assert got['stale']==401 and got['disabled']==401 and got['expired']==401
    assert got['agency_mismatch']==403 and got['source_mismatch']==403
    assert got['source_cannot_agency']==401 and got['scoped_cannot_generic']==401
    assert got['nonces'] >= 3 and got['expired_nonce_count']==0
