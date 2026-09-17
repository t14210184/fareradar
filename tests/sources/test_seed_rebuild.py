import json,pathlib,sqlite3,subprocess
ROOT=pathlib.Path(__file__).resolve().parents[2]
def test_clean_db_rebuild_with_seeds():
    subprocess.run(['python3','scripts/compile_seeds.py'],cwd=ROOT,check=True,capture_output=True,text=True)
    db=sqlite3.connect(':memory:')
    for p in sorted((ROOT/'migrations').glob('*.sql')): db.executescript(p.read_text())
    db.executescript((ROOT/'generated/seed.generated.sql').read_text())
    source_rows=json.loads((ROOT/'config/sources.seed.json').read_text())
    expected_sources=len(source_rows)
    expected_providers=len(json.loads((ROOT/'config/providers.seed.json').read_text()))
    assert db.execute('select count(*) from source_registry').fetchone()[0]==expected_sources
    assert db.execute('select count(*) from provider_access_registry').fetchone()[0]==expected_providers
    expected_shadow=sum(r['lifecycle_state']=='SHADOW' for r in source_rows)
    expected_discovered=sum(r['lifecycle_state']=='DISCOVERED' for r in source_rows)
    assert db.execute("select count(*) from source_registry where lifecycle_state='SHADOW'").fetchone()[0]==expected_shadow
    assert db.execute("select count(*) from source_registry where lifecycle_state='DISCOVERED'").fetchone()[0]==expected_discovered
    # Research seeds are inert until access/terms review explicitly clears the legacy kill switch.
    assert db.execute("select count(*) from source_registry where terms_snapshot_at='RECHECK_REQUIRED' and kill_switch<>1").fetchone()[0]==0
    assert db.execute("select count(*) from source_registry where lifecycle_state in ('SHADOW','ENABLED') and kill_switch=0 and terms_snapshot_at<>'RECHECK_REQUIRED'").fetchone()[0]==0
