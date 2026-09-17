import pathlib, subprocess
ROOT=pathlib.Path(__file__).resolve().parents[1]
def test_schema_invariants():
    p=subprocess.run(['python3','scripts/validate_invariants.py'],cwd=ROOT,text=True,capture_output=True,check=True)
    assert 'SCHEMA_INVARIANTS_PASS' in p.stdout
