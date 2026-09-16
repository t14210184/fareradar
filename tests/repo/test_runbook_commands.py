import json,pathlib,subprocess
ROOT=pathlib.Path(__file__).resolve().parents[2]
def test_documented_local_release_commands_exist_and_plan_is_read_only():
    pkg=json.loads((ROOT/'package.json').read_text()); runbook=(ROOT/'docs/RUNBOOK.md').read_text()
    for name in ['preflight','deploy:plan','gates','check:invariants']:
        assert name in pkg['scripts']
    assert 'npm run preflight' in runbook and 'npm run deploy:plan' in runbook
    assert 'npm run deploy:cloudflare' not in runbook
    p=subprocess.run(['python3','scripts/deploy_plan.py'],cwd=ROOT,text=True,capture_output=True,check=True)
    got=json.loads(p.stdout); assert got['mutation_allowed'] is False and got['reason']=='READ_ONLY_DEPLOY_PLAN_REQUIRES_PROVIDER_MUTATION_PERMIT' and len(got['ordered_shared_steps'])>=1
