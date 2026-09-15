import json,pathlib,subprocess
ROOT=pathlib.Path(__file__).resolve().parents[2]
def test_scoped_roles_cannot_escape_or_cross_entity_even_with_broad_paths():
    p=subprocess.run(['node','tests/node_scoped_role_boundary.mjs'],cwd=ROOT,text=True,capture_output=True,check=True)
    got=json.loads(p.stdout)
    assert got['agency_operational']==401
    assert got['email_operational']==401
    assert got['provider_operational']==401
    assert got['agency_unbound']==401
    assert got['email_unbound']==401
    assert got['provider_unbound']==401
    assert got['cross_pricing']==403 and got['cross_payment']==403
    assert got['other_pricing']==0 and got['other_payment']==0
    assert got['source_state']=='SHADOW'
