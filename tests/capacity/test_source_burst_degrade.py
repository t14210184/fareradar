def test_burst_degrades_or_quarantines(run_cli):
    assert run_cli('burst-decision',{'queue':2000,'duplicates':0,'schemaDrift':0})=='DOWNSHIFT'
    assert run_cli('burst-decision',{'queue':10,'duplicates':0,'schemaDrift':30})=='QUARANTINE'


def test_independent_source_burst_triggers_only_unverified_provisional():
    import json, pathlib, subprocess
    root=pathlib.Path(__file__).resolve().parents[2]
    p=subprocess.run(['node','tests/node_social_heat_burst.mjs'],cwd=root,text=True,capture_output=True,check=True)
    x=json.loads(p.stdout)
    assert x['two']['triggered'] is False and x['two']['reason']=='INDEPENDENT_SOURCE_THRESHOLD_NOT_MET'
    assert x['positive']['triggered'] is True and x['positive']['reason']=='INDEPENDENT_SOURCE_BURST'
    assert x['positive']['independent_source_count']==3
    assert x['replay']['triggered'] is True and x['intents']==1
    assert x['heat']['independent_source_count']==3 and x['heat']['route_relevant']==1
    assert x['priority']>=90
    assert x['payload']['kind']=='P0-PROVISIONAL'
    assert x['payload']['verification_state']=='UNVERIFIED'
    assert x['payload']['actionable'] is False and x['payload']['bookable'] is False
    assert x['payload']['provisional_trigger']['rule']=='INDEPENDENT_SOURCE_BURST_V1'
    assert x['routeMismatch']['triggered'] is False and x['routeMismatch']['reason']=='ROUTE_NOT_RELEVANT'
