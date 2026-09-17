def test_all_price_beat_conditions_required(run_cli):
    x={'same_route':True,'same_date':True,'comparable_fare':True,'competitor_official':True,'within_window':True}; assert run_cli('price-beat',x) is True
    x['competitor_official']=False; assert run_cli('price-beat',x) is False
