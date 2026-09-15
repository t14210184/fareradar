import json,pathlib,subprocess
ROOT=pathlib.Path(__file__).resolve().parents[2]
def test_documented_local_release_commands_exist_and_plan_is_read_only():
    pkg=json.loads((ROOT/'package.json').read_text()); runbook=(ROOT/'docs/RUNBOOK.md').read_text()
    for name in ['preflight','deploy:plan','gates','check:invariants']:
        assert name in pkg['scripts']
    assert 'npm run preflight' in runbook and 'npm run deploy:plan' in runbook
    assert 'npm run deploy:cloudflare' not in runbook
    p=subprocess.run(['python3','scripts/deploy_plan.py'],cwd=ROOT,text=True,capture_output=True,check=True)
    got=json.loads(p.stdout); assert got['mutation_allowed'] is False and got['code_ready'] is True
