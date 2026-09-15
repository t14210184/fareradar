def test_win11_offline_only_degrades_heavy_verifier(run_cli):
    got=run_cli('win11-state',False); assert got=={'system':'DEGRADED','heavy_verifier':'UNAVAILABLE'}
