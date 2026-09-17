import json, pathlib, subprocess
ROOT=pathlib.Path(__file__).resolve().parents[2]

def test_source_onboarding_requires_evidence_shadow_then_enable():
    p=subprocess.run(['node','tests/node_source_onboarding.mjs'],cwd=ROOT,text=True,capture_output=True,check=True)
    x=json.loads(p.stdout)
    assert x['directEnableBlocked'] is True
    assert x['before']['inserted']==0
    assert x['shadow']['state']=='SHADOW' and x['shadow']['idempotent'] is False
    assert x['afterShadow']['inserted']==1 and x['jobs']==1
    assert x['incompleteEnableBlocked'] is True
    assert x['enabled']['state']=='ENABLED' and x['idem']['idempotent'] is True
    assert x['reviews']==2
    assert x['disabled']['state']=='DISABLED'
    assert x['source']['lifecycle_state']=='DISABLED' and x['source']['kill_switch']==1 and x['source']['kill_switch_state']=='TRIPPED'
