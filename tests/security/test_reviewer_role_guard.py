import json, pathlib, subprocess
ROOT=pathlib.Path(__file__).resolve().parents[2]
def test_reviewer_roles_cannot_escape_even_with_broad_path_allowlist():
    p=subprocess.run(['node','tests/node_reviewer_role_guard.mjs'],cwd=ROOT,text=True,capture_output=True,check=True)
    assert json.loads(p.stdout)['ok'] is True
