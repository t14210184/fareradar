import json,pathlib,subprocess
ROOT=pathlib.Path(__file__).resolve().parents[2]
def test_immutable_offer_and_provider_gates():
    p=subprocess.run(['node','tests/node_offers.mjs'],cwd=ROOT,text=True,capture_output=True,check=True); x=json.loads(p.stdout)
    assert x['first']['idempotent'] is False and x['second']['idempotent'] is True and x['count']==1
    assert x['conflict'] is True and x['lcc'] is True and x['stale'] is True
