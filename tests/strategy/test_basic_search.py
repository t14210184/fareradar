def test_strategy_catalog_and_pareto(run_cli):
    ids=run_cli('strategies',None); assert ids==[f'S{i:02d}' for i in range(20)]
    items=[{'id':'a','cash':5000,'elapsed':5,'risk':1,'tickets':1},{'id':'b','cash':6000,'elapsed':6,'risk':2,'tickets':2},{'id':'c','cash':4500,'elapsed':8,'risk':2,'tickets':2}]
    got=run_cli('bounded-expand',{'items':items,'maxTickets':4}); assert [x['id'] for x in got]==['a','c']

def test_strategy_search_enforces_level_threshold_flags_profile_limits_and_pareto(run_cli):
    items=[
      {'id':'direct','strategy_id':'S00','cash':9000,'elapsed':4,'risk':1,'tickets':1,'estimated_saving_vs_baseline':0,'route_prior':1},
      {'id':'alt-low-saving','strategy_id':'S05','cash':8500,'elapsed':5,'risk':1,'tickets':1,'estimated_saving_vs_baseline':500,'route_prior':3},
      {'id':'kr-self','strategy_id':'S09','cash':7000,'elapsed':8,'risk':3,'tickets':2,'estimated_saving_vs_baseline':2500,'route_prior':4,'self_transfers':1},
      {'id':'kr-too-many-self','strategy_id':'S09','cash':6500,'elapsed':9,'risk':4,'tickets':3,'estimated_saving_vs_baseline':3000,'route_prior':5,'self_transfers':2},
      {'id':'mainland','strategy_id':'S11','cash':6000,'elapsed':8,'risk':4,'tickets':2,'estimated_saving_vs_baseline':3500,'route_prior':2,'self_transfers':1},
      {'id':'nested','strategy_id':'S15','cash':5500,'elapsed':10,'risk':5,'tickets':4,'estimated_saving_vs_baseline':4000,'route_prior':1},
      {'id':'dominated','strategy_id':'S07','cash':9500,'elapsed':7,'risk':2,'tickets':1,'estimated_saving_vs_baseline':2000,'route_prior':2},
    ]
    opt={'expansion_threshold':1500,'max_tickets':3,'max_self_transfers':1,'max_overnights':1,'max_nodes':20,'mainland_enabled':False,'advanced_enabled':False}
    got=run_cli('strategy-search',{'items':items,'options':opt})
    assert [x['id'] for x in got]==['kr-self','direct']
    opt['mainland_enabled']=True
    got=run_cli('strategy-search',{'items':items,'options':opt})
    assert [x['id'] for x in got]==['mainland','kr-self','direct']


def test_strategy_search_is_bounded_and_deterministic(run_cli):
    items=[{'id':f'x{i}','strategy_id':'S04','cash':7000+i,'elapsed':6+i/10,'risk':2,'tickets':1,'estimated_saving_vs_baseline':2000,'route_prior':i} for i in range(20)]
    opt={'expansion_threshold':1000,'max_tickets':4,'max_self_transfers':1,'max_overnights':1,'max_nodes':5}
    a=run_cli('strategy-search',{'items':items,'options':opt})
    b=run_cli('strategy-search',{'items':list(reversed(items)),'options':opt})
    assert a==b
    assert len(a)<=5
