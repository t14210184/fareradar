def test_foreign_origin_full_cycle_cost(run_cli):
    got=run_cli('foreign-cycle-cost',{'main':8000,'positioning':2500,'tail':1800,'taxes':1500,'hotel':1200,'ground':500,'documents':0}); assert got==15500
