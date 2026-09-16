import json, pathlib
ROOT=pathlib.Path(__file__).resolve().parents[2]

def test_single_minute_cron_multiplexes_heavy_phase():
    cfg=json.loads((ROOT/'wrangler.jsonc').read_text())
    assert cfg['triggers']['crons']==['* * * * *']
    worker=(ROOT/'src/worker.ts').read_text()
    assert 'tick.getUTCMinutes()%5===0' in worker
    assert 'event?.cron==="*/5 * * * *"' not in worker
    assert 'await planDueCandidateSearches' in worker and 'await dispatchProviderSearchPlans' in worker
    assert 'await projectAlertIntents' in worker and 'await scheduleDueSources' in worker
