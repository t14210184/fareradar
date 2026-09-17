import json,pathlib,subprocess
ROOT=pathlib.Path(__file__).resolve().parents[2]
def test_promo_constraints_filter_exact_provider_queries():
    p=subprocess.run(['node','tests/node_promo_constraints.mjs'],cwd=ROOT,text=True,capture_output=True,check=True)
    x=json.loads(p.stdout)
    assert x['planned']['created']==1 and x['planned']['planned']==1
    q=x['queries'][0]
    assert q['slices']==[{'origin':'TPE','destination':'KIX','departure_date':'2026-11-04'},{'origin':'KIX','destination':'TPE','departure_date':'2026-11-07'}]
    assert x['expired']['reason']=='PROMOTION_SALE_EXPIRED'
