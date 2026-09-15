def test_burst_degrades_or_quarantines(run_cli):
    assert run_cli('burst-decision',{'queue':2000,'duplicates':0,'schemaDrift':0})=='DOWNSHIFT'
    assert run_cli('burst-decision',{'queue':10,'duplicates':0,'schemaDrift':30})=='QUARANTINE'
