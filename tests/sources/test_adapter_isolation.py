def test_bad_source_quarantines_without_global_effect(run_cli):
    assert run_cli('adaptive-schedule',{'confirmed_rate':0,'first_win_rate':0,'duplicate_rate':0,'ghost_rate':0.1,'schema_drift_rate':0.5})=='QUARANTINE'
    assert run_cli('adaptive-schedule',{'confirmed_rate':0.8,'first_win_rate':0.5,'duplicate_rate':0.1,'ghost_rate':0.1,'schema_drift_rate':0}) in {'BOOST','KEEP'}
