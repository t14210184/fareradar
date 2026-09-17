-- SourceRegistry v1.3 contract completion
ALTER TABLE source_registry ADD COLUMN owner_type TEXT;
ALTER TABLE source_registry ADD COLUMN route_scope TEXT;
ALTER TABLE source_registry ADD COLUMN push_capable INTEGER DEFAULT 0 CHECK(push_capable IN (0,1));
ALTER TABLE source_registry ADD COLUMN discovery_trust TEXT;
ALTER TABLE source_registry ADD COLUMN lead_score REAL DEFAULT 0;
ALTER TABLE source_registry ADD COLUMN yield_score REAL DEFAULT 0;
ALTER TABLE source_registry ADD COLUMN fare_freshness TEXT;
ALTER TABLE source_registry ADD COLUMN requires_repricing INTEGER DEFAULT 1 CHECK(requires_repricing IN (0,1));
ALTER TABLE source_registry ADD COLUMN privacy_class TEXT;
ALTER TABLE source_registry ADD COLUMN max_burst INTEGER DEFAULT 1;
ALTER TABLE source_registry ADD COLUMN backoff_policy TEXT;
ALTER TABLE source_registry ADD COLUMN kill_switch_state TEXT DEFAULT 'CLEAR';
ALTER TABLE source_registry ADD COLUMN last_success_at TEXT;
ALTER TABLE source_registry ADD COLUMN last_unique_deal_at TEXT;
ALTER TABLE source_registry ADD COLUMN status TEXT;

-- SourceObservation v1.3 contract completion
ALTER TABLE source_observations ADD COLUMN published_at TEXT;
ALTER TABLE source_observations ADD COLUMN content_version INTEGER DEFAULT 1;
ALTER TABLE source_observations ADD COLUMN raw_ref TEXT;
ALTER TABLE source_observations ADD COLUMN access_basis_snapshot TEXT;
ALTER TABLE source_observations ADD COLUMN retention_until TEXT;
ALTER TABLE source_observations ADD COLUMN deleted_at_source TEXT;
ALTER TABLE source_observations ADD COLUMN correction_of_observation_id TEXT;

-- PromotionEvent v1.3 contract completion
ALTER TABLE promotion_events ADD COLUMN promotion_type TEXT;
ALTER TABLE promotion_events ADD COLUMN carrier_or_seller TEXT;
ALTER TABLE promotion_events ADD COLUMN route_scope TEXT;
ALTER TABLE promotion_events ADD COLUMN sale_window TEXT;
ALTER TABLE promotion_events ADD COLUMN travel_window TEXT;
ALTER TABLE promotion_events ADD COLUMN price_claim TEXT;
ALTER TABLE promotion_events ADD COLUMN currency TEXT;
ALTER TABLE promotion_events ADD COLUMN member_requirement TEXT;
ALTER TABLE promotion_events ADD COLUMN channel_requirement TEXT;
ALTER TABLE promotion_events ADD COLUMN first_observed_at TEXT;
ALTER TABLE promotion_events ADD COLUMN last_observed_at TEXT;
ALTER TABLE promotion_events ADD COLUMN cluster_fingerprint TEXT;
ALTER TABLE promotion_events ADD COLUMN primary_evidence_id TEXT;

CREATE TABLE IF NOT EXISTS route_universe_entries (
  route_id TEXT PRIMARY KEY, origin_airport TEXT NOT NULL, destination_airport TEXT NOT NULL,
  carrier_alias_id TEXT, service_type TEXT NOT NULL, first_seen_at TEXT NOT NULL, last_seen_at TEXT NOT NULL,
  status TEXT NOT NULL, official_evidence_id TEXT NOT NULL REFERENCES source_observations(observation_id)
);
CREATE TABLE IF NOT EXISTS source_discovery_edges (
  from_source_id TEXT NOT NULL REFERENCES source_registry(source_id), to_candidate_source_key TEXT NOT NULL,
  relation_type TEXT NOT NULL, observed_at TEXT NOT NULL, evidence_id TEXT NOT NULL,
  confidence REAL NOT NULL CHECK(confidence>=0 AND confidence<=1), onboarding_state TEXT NOT NULL,
  PRIMARY KEY(from_source_id,to_candidate_source_key,relation_type,evidence_id)
);

-- SourceHealthWindow v1.3 contract completion
ALTER TABLE source_health_windows ADD COLUMN window_start TEXT;
ALTER TABLE source_health_windows ADD COLUMN window_end TEXT;
ALTER TABLE source_health_windows ADD COLUMN unique_event_count INTEGER DEFAULT 0;
ALTER TABLE source_health_windows ADD COLUMN median_lead_seconds REAL;
ALTER TABLE source_health_windows ADD COLUMN fetch_error_rate REAL;
ALTER TABLE source_health_windows ADD COLUMN mean_request_cost REAL;
ALTER TABLE source_health_windows ADD COLUMN mean_cpu_ms REAL;
ALTER TABLE source_health_windows ADD COLUMN recommended_schedule_action TEXT;
