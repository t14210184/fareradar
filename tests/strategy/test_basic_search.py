def test_strategy_catalog_and_pareto(run_cli):
    ids=run_cli('strategies',None); assert ids==[f'S{i:02d}' for i in range(20)]
    items=[{'id':'a','cash':5000,'elapsed':5,'risk':1,'tickets':1},{'id':'b','cash':6000,'elapsed':6,'risk':2,'tickets':2},{'id':'c','cash':4500,'elapsed':8,'risk':2,'tickets':2}]
    got=run_cli('bounded-expand',{'items':items,'maxTickets':4}); assert [x['id'] for x in got]==['a','c']
