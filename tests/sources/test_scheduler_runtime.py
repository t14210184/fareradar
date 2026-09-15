import json,pathlib,subprocess
ROOT=pathlib.Path(__file__).resolve().parents[2]
def test_registry_to_job_to_health_runtime():
    p=subprocess.run(['node','tests/node_scheduler.mjs'],cwd=ROOT,text=True,capture_output=True,check=True); x=json.loads(p.stdout)
    assert x['a']['inserted']==1 and x['b']['inserted']==0
    assert x['leased']==1 and x['health']['action']=='KEEP'
    assert x['c']['inserted']==1 and x['job_count']==2
    assert x['s2_jobs']==0
    assert x['fetch']['etag']=='"a"' and x['fetch']['content_sha256']=='a'*64
    assert x['health_row']['window_start'].startswith('2026-09-15') and x['health_row']['recommended_schedule_action']=='KEEP'
