def test_route_diff_only_onboards_never_confirms(run_cli):
    diff=run_cli('route-diff',{'before':['TPE-NRT'],'after':['TPE-NRT','KHH-KMQ']}); assert diff==['KHH-KMQ']
    rows=run_cli('onboarding',diff); assert rows==[{'route':'KHH-KMQ','state':'DISCOVERED','confirmed_fare':False}]
