from __future__ import annotations
import pathlib, sqlite3
ROOT=pathlib.Path(__file__).resolve().parents[1]
db=sqlite3.connect(':memory:')
for p in sorted((ROOT/'migrations').glob('*.sql')): db.executescript(p.read_text())
required={
'itinerary_candidates':{'itinerary_id','strategy_type','verification_state'},
'offer_snapshots':{'provider_offer_id','query_fingerprint','provider','raw_sha256','offer_total','fare_freshness','cached_or_live'},
'ticket_components':{'ticket_id','pnr_group','connection_protection_type'},
'transfer_boundaries':{'from_ticket_id','to_ticket_id','scheduled_buffer_minutes','required_buffer_minutes','evidence_id'},
'cost_components':{'inclusion_state','source_offer_id','policy_evidence_id','dedupe_key','paid_state','refundable'},
'readiness_facets':{'facet_type','status','expires_at','authority','evidence_id'},
'document_requirements':{'jurisdiction','travel_event','traveler_document_class','valid_for_event_at','authority_source','source_snapshot_id'},
'four_leg_liabilities':{'cycle_id','component_type','remaining_exposure','recoverable_amount'},
'audit_evidence':{'gate_id','spec_version','test_report_hash','provider_readback','unresolved_items'},
'source_registry':{'source_id','owner_type','source_class','canonical_domain_or_account','market','language','currency','route_scope','access_basis','fetch_method','push_capable','discovery_trust','verification_authority','lead_score','yield_score','fare_freshness','requires_repricing','parser','terms_snapshot_at','privacy_class','retention_policy','min_interval_ms','max_burst','backoff_policy','kill_switch_state','last_success_at','last_unique_deal_at','status'},
'source_observations':{'observation_id','source_id','canonical_url','published_at','observed_at','content_sha256','content_version','raw_ref','parser_version','access_basis_snapshot','retention_until','deleted_at_source','correction_of_observation_id'},
'promotion_events':{'event_id','promotion_type','carrier_or_seller','market','route_scope','sale_window','travel_window','price_claim','currency','promo_code','member_requirement','channel_requirement','state','first_observed_at','last_observed_at','cluster_fingerprint','primary_evidence_id'},
'agency_inventory_offers':{'agency_offer_id','agency_id','seller_verification_state','allotment_type','origin','destination','price','booking_or_contact_channel','source_evidence_id','state'},
'route_universe_entries':{'route_id','origin_airport','destination_airport','carrier_alias_id','service_type','first_seen_at','last_seen_at','status','official_evidence_id'},
'source_discovery_edges':{'from_source_id','to_candidate_source_key','relation_type','observed_at','evidence_id','confidence','onboarding_state'},
'email_evidence':{'message_id','source_id','from_domain','body_sha256','dkim_result','spf_result','dmarc_result','canonical_links_json','expanded_links_json','link_risk_class','trust_class','retention_until'},
'source_health_windows':{'source_id','window_start','window_end','fetch_count','success_count','unique_event_count','confirmed_count','ghost_count','duplicate_count','first_win_count','median_lead_seconds','fetch_error_rate','mean_request_cost','mean_cpu_ms','schema_drift_count','recommended_schedule_action'},
'verification_jobs':{'job_id','target_class','source_id','state','attempts','available_at','lease_until'},
'source_outcome_attributions':{'attribution_id','itinerary_id','source_id','observation_id','outcome_type','first_win','window_date','observed_at','confirmed_at'},
'search_campaigns':{'campaign_id','profile_id','provider_id','departure_dates_json','trip_lengths_json','passengers_json','max_queries_per_signal','enabled','expires_at'},
'provider_search_plans':{'plan_id','campaign_id','queue_id','provider_id','query_fingerprint','query_json','state','provider_job_id','next_attempt_at'},
'candidate_offer_links':{'queue_id','plan_id','job_id','provider_offer_id','query_fingerprint'},
'candidate_verification_results':{'result_id','queue_id','query_fingerprint','verification_state','reason','best_offer_id','live_offer_count','provider_count'} }
for table, cols in required.items():
    got={r[1] for r in db.execute(f'pragma table_info({table})')}
    missing=cols-got
    if missing: raise SystemExit(f'{table}: missing {sorted(missing)}')
print('SCHEMA_INVARIANTS_PASS')
