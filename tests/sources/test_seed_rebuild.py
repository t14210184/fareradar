import json,pathlib,sqlite3,subprocess
ROOT=pathlib.Path(__file__).resolve().parents[2]
def test_clean_db_rebuild_with_seeds():
    subprocess.run(['python3','scripts/compile_seeds.py'],cwd=ROOT,check=True,capture_output=True,text=True)
    db=sqlite3.connect(':memory:')
    for p in sorted((ROOT/'migrations').glob('*.sql')): db.executescript(p.read_text())
    db.executescript((ROOT/'generated/seed.generated.sql').read_text())
    expected_sources=len(json.loads((ROOT/'config/sources.seed.json').read_text()))
    expected_providers=len(json.loads((ROOT/'config/providers.seed.json').read_text()))
    assert db.execute('select count(*) from source_registry').fetchone()[0]==expected_sources
    assert db.execute('select count(*) from provider_access_registry').fetchone()[0]==expected_providers
    assert db.execute("select count(*) from source_registry where lifecycle_state='SHADOW'").fetchone()[0]==expected_sources
