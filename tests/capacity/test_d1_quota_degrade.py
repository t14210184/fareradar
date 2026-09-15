def test_critical_work_survives_quota_pressure(run_cli):
    got=run_cli('quota-degrade',0.96); assert got['mode']=='CRITICAL_ONLY'; assert set(got['keep'])=={'P0_INGEST','OUTBOX','HEARTBEAT'}
