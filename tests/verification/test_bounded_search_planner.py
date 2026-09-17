import json, pathlib, subprocess
ROOT=pathlib.Path(__file__).resolve().parents[2]

def test_private_campaign_generates_only_bounded_exact_queries_and_dispatches_fail_closed():
    p=subprocess.run(['node','tests/node_search_planner.mjs'],cwd=ROOT,text=True,capture_output=True,check=True)
    x=json.loads(p.stdout)
    assert x['planned']['created']==2 and x['planned']['planned']==2
    queries=[r['query'] for r in x['plansBefore']]
    assert all(q['slices'][0]['departure_date']=='2026-11-02' for q in queries)
    assert sorted(q['slices'][1]['departure_date'] for q in queries)==['2026-11-05','2026-11-09']
    assert x['deferred']=={'considered':2,'dispatched':0,'deferred':2,'dead':0}
    assert x['dispatched']=={'considered':2,'dispatched':2,'deferred':0,'dead':0}
    assert all(j['target_class']=='PROVIDER_API' and j['provider_mode']=='BACKGROUND' and j['provider_id']=='duffel' for j in x['jobs'])
    assert x['consumers']==2
