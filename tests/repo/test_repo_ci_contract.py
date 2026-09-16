import json, pathlib
ROOT=pathlib.Path(__file__).resolve().parents[2]

def test_ci_contract_present_and_pins_wrangler_dry_run():
    ci=(ROOT/'.github/workflows/ci.yml').read_text()
    pkg=json.loads((ROOT/'package.json').read_text())
    assert 'npm run check:wrangler' in ci
    cmd=pkg['scripts']['check:wrangler']
    assert 'npm run build' in cmd
    assert 'wrangler@4.131.2 deploy --dry-run --config wrangler.ci.jsonc' in cmd

def test_ci_wrangler_uses_synthetic_d1_but_production_stays_fail_closed():
    ci=json.loads((ROOT/'wrangler.ci.jsonc').read_text())
    prod=json.loads((ROOT/'wrangler.jsonc').read_text())
    assert ci['triggers']['crons']==['* * * * *']
    assert prod['triggers']['crons']==['* * * * *']
    assert ci['d1_databases'][0]['database_id']=='00000000-0000-0000-0000-000000000001'
    assert prod['d1_databases'][0]['database_id']=='REPLACE_WITH_D1_DATABASE_ID'
    assert ci['d1_databases'][0]['database_id'] != prod['d1_databases'][0]['database_id']
