def test_foreign_origin_full_cycle_cost(run_cli):
    got=run_cli('foreign-cycle-cost',{'main':8000,'positioning':2500,'tail':1800,'taxes':1500,'hotel':1200,'ground':500,'documents':0}); assert got==15500

def test_four_leg_cycle_state_and_liability_runtime():
    import json, pathlib, subprocess
    root=pathlib.Path(__file__).resolve().parents[2]
    p=subprocess.run(['node','tests/node_four_leg_cycle.mjs'],cwd=root,text=True,capture_output=True,check=True)
    x=json.loads(p.stdout)
    assert x['created']['state']=='NOT_STARTED'
    assert x['before']['remaining_exposure']==10900 and x['before']['unrealized_positioning_liability'] is True
    assert x['illegal']=='FOUR_LEG_ILLEGAL_TRANSITION'
    assert x['sequence'][-1]=='CYCLE_COMPLETED'
    assert x['after']['unrealized_positioning_liability'] is False
    assert x['terminal']=='FOUR_LEG_ILLEGAL_TRANSITION'
    assert x['state']=={'state':'BROKEN','broken_reason':'POSITIONING_MISSED'}
