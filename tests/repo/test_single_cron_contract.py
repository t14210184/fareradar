import json, pathlib, re
ROOT=pathlib.Path(__file__).resolve().parents[2]
def _jsonc(path):
    return json.loads(re.sub(r'//.*','',path.read_text()))
def test_production_and_ci_use_one_minute_cron_only():
    assert _jsonc(ROOT/'wrangler.jsonc')['triggers']['crons']==['* * * * *']
    assert _jsonc(ROOT/'wrangler.ci.jsonc')['triggers']['crons']==['* * * * *']
def test_worker_uses_modulo_phase_not_second_cron_literal():
    s=(ROOT/'src/worker.ts').read_text()
    assert 'minute%5===0' in s
    assert '*/5 * * * *' not in s
