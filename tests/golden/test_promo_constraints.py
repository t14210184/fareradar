def test_direction_weekday_sale_window(run_cli):
    promo={'direction':'TPE-KIX','required_weekdays':[2,3],'sale_from':'2026-09-15T00:00:00Z','sale_to':'2026-09-16T00:00:00Z'}
    assert run_cli('promo-eligible',{'promo':promo,'query':{'direction':'TPE-KIX','weekday':2,'at':'2026-09-15T03:00:00Z'}}) is True
    assert run_cli('promo-eligible',{'promo':promo,'query':{'direction':'KIX-TPE','weekday':2,'at':'2026-09-15T03:00:00Z'}}) is False
    assert run_cli('promo-eligible',{'promo':promo,'query':{'direction':'TPE-KIX','weekday':6,'at':'2026-09-15T03:00:00Z'}}) is False
