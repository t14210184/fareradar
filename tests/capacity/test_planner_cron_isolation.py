import json, pathlib
ROOT=pathlib.Path(__file__).resolve().parents[2]

def test_provider_planner_uses_single_cron_with_modulo_phase():
    cfg=json.loads((ROOT/'wrangler.jsonc').read_text())
    assert cfg['triggers']['crons']==['* * * * *']
    worker=(ROOT/'src/worker.ts').read_text()
    assert 'minute%5===0' in worker
    assert '*/5 * * * *' not in worker
    assert 'await planDueCandidateSearches' in worker and 'await dispatchProviderSearchPlans' in worker
    assert 'await projectAlertIntents' in worker
