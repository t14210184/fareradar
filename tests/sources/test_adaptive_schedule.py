def test_schedule_deterministic(run_cli):
    assert run_cli('adaptive-schedule',{'confirmed_rate':0.9,'first_win_rate':0.8,'duplicate_rate':0.0,'ghost_rate':0.0,'schema_drift_rate':0.0})=='BOOST'
    assert run_cli('adaptive-schedule',{'confirmed_rate':0.0,'first_win_rate':0.0,'duplicate_rate':0.9,'ghost_rate':0.0,'schema_drift_rate':0.0})=='DOWNSHIFT'
    assert run_cli('adaptive-schedule',{'confirmed_rate':0.0,'first_win_rate':0.0,'duplicate_rate':0.0,'ghost_rate':0.8,'schema_drift_rate':0.0})=='QUARANTINE'
