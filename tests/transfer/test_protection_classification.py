def test_same_pnr_does_not_imply_protected(run_cli):
    got=run_cli('protection',{'protectionType':'UNKNOWN','evidenceId':'e1','samePnr':True}); assert got['accepted'] is False
    got=run_cli('protection',{'protectionType':'THROUGH_TICKET_CARRIER_PROTECTED','evidenceId':None,'samePnr':True}); assert got['accepted'] is False
