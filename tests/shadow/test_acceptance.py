def mk(day, i):
    return {'day':day,'complex':i<3,'source_discovery':i<3,'agency_clearance':i==0,'safety_errors':0,'reviewed':True,'false_actionable':False}
def test_shadow_evaluator_requires_real_thresholds(run_cli):
    small=[mk('2026-09-01',i) for i in range(20)]; assert run_cli('shadow-acceptance',small)['pass'] is False
    rows=[]
    for d in range(14):
        day=f'2026-09-{d+1:02d}'
        for i in range(12): rows.append(mk(day,i))
    got=run_cli('shadow-acceptance',rows); assert got['pass'] is True and got['labeled']>=150 and got['complex']>=30 and got['safety_errors']==0
