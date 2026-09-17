def test_all_complex_samples_reviewed_and_no_false_actionable(run_cli):
    rows=[{'day':'2026-09-01','complex':True,'source_discovery':False,'agency_clearance':False,'safety_errors':0,'reviewed':True,'false_actionable':False} for _ in range(30)]
    assert run_cli('shadow-complex-review',rows)['pass'] is True
    rows[0]['false_actionable']=True; assert run_cli('shadow-complex-review',rows)['pass'] is False
