import json, pathlib
ROOT=pathlib.Path(__file__).resolve().parents[2]

def test_provider_planner_uses_separate_low_frequency_cron():
    cfg=json.loads((ROOT/'wrangler.jsonc').read_text())
    assert cfg['triggers']['crons']==['* * * * *','*/5 * * * *']
    worker=(ROOT/'src/worker.ts').read_text()
    assert 'event?.cron==="*/5 * * * *"' in worker
    assert 'await planDueCandidateSearches' in worker and 'await dispatchProviderSearchPlans' in worker
    assert 'return;} await projectAlertIntents' in worker
