import json, pathlib
ROOT=pathlib.Path(__file__).resolve().parents[2]
def test_source_contract_fields_and_unique_ids():
    rows=json.loads((ROOT/'config/sources.seed.json').read_text()); ids=[r['source_id'] for r in rows]; assert len(ids)==len(set(ids))
    required=['owner_type','source_class','canonical_domain_or_account','market','language','currency','route_scope','access_basis','fetch_method','push_capable','discovery_trust','verification_authority','lead_score','yield_score','fare_freshness','requires_repricing','parser','terms_snapshot_at','privacy_class','retention_policy','min_interval_ms','max_burst','backoff_policy','kill_switch_state','status']
    for r in rows:
        for k in required: assert k in r and r[k] is not None

def test_v13_research_seed_coverage_is_materialized_fail_closed():
    rows=json.loads((ROOT/'config/sources.seed.json').read_text()); by={r['source_id']:r for r in rows}
    required_ids={
        'tigerair_tw_official','china_airlines_tw_japan','eva_tw_japan','starlux_promotions','peach_tw_official',
        'jal_tw_official','ana_tw_deals','trinity_airways_official','jejuair_events','cathay_tw_official','hkexpress_official',
        'liontravel_earlybird','colatour_official','settour_flight','lifetour_official','tripcom_tw_flights',
        'ptt_japan_travel','flyertalk_forum','traicy_sales','aeroroutes','secret_flying','jnto_tw_airline_routes',
        'google_flights_price_email','skyscanner_price_email','peach_newsletter','tigerair_newsletter'
    }
    assert required_ids <= set(by)
    assert len(rows) >= 27
    # Research seeds are candidates, not authorization. Until PG25/PG31 refreshes terms/access,
    # polling must remain hard-disabled even when the lifecycle is SHADOW.
    for r in rows:
        if r['terms_snapshot_at']=='RECHECK_REQUIRED':
            assert r['kill_switch']==1
            assert r['status'] in {'SHADOW','DISCOVERED'}
    for sid in ('google_flights_price_email','skyscanner_price_email','peach_newsletter','tigerair_newsletter'):
        assert by[sid]['push_capable'] is True
        assert by[sid]['entrypoint_url'] is None
        assert by[sid]['fetch_method']=='EMAIL_PUSH'
