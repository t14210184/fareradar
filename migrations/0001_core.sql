PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS source_registry (
  source_id TEXT PRIMARY KEY, source_class TEXT NOT NULL, canonical_domain_or_account TEXT NOT NULL,
  entrypoint_url TEXT, access_basis TEXT NOT NULL, fetch_method TEXT NOT NULL, lifecycle_state TEXT NOT NULL,
  verification_authority TEXT NOT NULL, terms_snapshot_at TEXT, min_interval_ms INTEGER NOT NULL DEFAULT 300000,
  kill_switch INTEGER NOT NULL DEFAULT 1 CHECK(kill_switch IN (0,1))
);
CREATE TABLE IF NOT EXISTS provider_access_registry (
  provider_id TEXT PRIMARY KEY, access_basis TEXT NOT NULL, terms_snapshot_at TEXT, rate_policy TEXT,
  look_to_book_budget INTEGER, kill_switch_state TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS promotion_channel_registry (
  channel_id TEXT PRIMARY KEY, source_id TEXT NOT NULL REFERENCES source_registry(source_id), channel_type TEXT NOT NULL,
  enabled INTEGER NOT NULL DEFAULT 0 CHECK(enabled IN (0,1))
);
CREATE TABLE IF NOT EXISTS agency_partner_registry (
  agency_id TEXT PRIMARY KEY, source_id TEXT, status TEXT NOT NULL, verified_business INTEGER NOT NULL DEFAULT 0,
  terms_snapshot_at TEXT
);
CREATE TABLE IF NOT EXISTS source_observations (
  observation_id TEXT PRIMARY KEY, source_id TEXT NOT NULL, observed_at TEXT NOT NULL, canonical_url TEXT,
  content_sha256 TEXT NOT NULL, parser_version TEXT, access_basis TEXT NOT NULL, privacy_class TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS source_extractions (
  extraction_id TEXT PRIMARY KEY, observation_id TEXT NOT NULL REFERENCES source_observations(observation_id) ON DELETE CASCADE,
  extraction_type TEXT NOT NULL, payload_json TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS domain_outbox (
  id INTEGER PRIMARY KEY AUTOINCREMENT, event_type TEXT NOT NULL, entity_id TEXT NOT NULL, payload_json TEXT NOT NULL,
  state TEXT NOT NULL DEFAULT 'PENDING', attempts INTEGER NOT NULL DEFAULT 0, lease_until TEXT, created_at TEXT NOT NULL,
  UNIQUE(event_type, entity_id)
);
CREATE TABLE IF NOT EXISTS notification_outbox (
  notification_id TEXT PRIMARY KEY, channel_class TEXT NOT NULL, payload_json TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'PENDING',
  attempts INTEGER NOT NULL DEFAULT 0, next_attempt_at TEXT, lease_until TEXT, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS candidate_alert_intents (
  intent_id TEXT PRIMARY KEY, itinerary_id TEXT NOT NULL, alert_class TEXT NOT NULL, payload_json TEXT NOT NULL,
  projected_at TEXT, created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS itinerary_candidates (
  itinerary_id TEXT PRIMARY KEY, strategy_type TEXT NOT NULL, cash_trip_cost_twd REAL,
  cost_complete INTEGER NOT NULL CHECK(cost_complete IN (0,1)), risk_adjusted_cost_twd REAL, scenario_cost_json TEXT,
  generalized_cost_twd REAL, risk_class TEXT NOT NULL, verification_state TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS candidate_plan_intakes (
  intake_id TEXT PRIMARY KEY, itinerary_id TEXT NOT NULL REFERENCES itinerary_candidates(itinerary_id) DEFERRABLE INITIALLY DEFERRED,
  payload_sha256 TEXT NOT NULL, observed_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS offer_snapshots (
  provider_offer_id TEXT PRIMARY KEY, itinerary_id TEXT, query_fingerprint TEXT NOT NULL, provider TEXT NOT NULL,
  market TEXT, locale TEXT, currency TEXT NOT NULL, passenger_mix TEXT, baggage_query TEXT, observed_at TEXT NOT NULL,
  expires_at TEXT, raw_sha256 TEXT NOT NULL, source_snapshot_id TEXT, offer_total REAL NOT NULL,
  fare_freshness TEXT NOT NULL, cached_or_live TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS ticket_components (
  ticket_id TEXT PRIMARY KEY, itinerary_id TEXT NOT NULL REFERENCES itinerary_candidates(itinerary_id) ON DELETE CASCADE,
  pnr_group TEXT NOT NULL, provider TEXT NOT NULL, ticket_type TEXT NOT NULL, connection_protection_type TEXT NOT NULL,
  validating_carrier TEXT, ticket_stock TEXT, segments_json TEXT NOT NULL, fare_brand TEXT, refund_rule TEXT, change_rule TEXT
);
CREATE TABLE IF NOT EXISTS transfer_boundaries (
  boundary_id TEXT PRIMARY KEY, itinerary_id TEXT NOT NULL REFERENCES itinerary_candidates(itinerary_id) ON DELETE CASCADE,
  from_ticket_id TEXT NOT NULL REFERENCES ticket_components(ticket_id), to_ticket_id TEXT NOT NULL REFERENCES ticket_components(ticket_id),
  airport TEXT NOT NULL, self_transfer INTEGER NOT NULL CHECK(self_transfer IN (0,1)), protection_type TEXT NOT NULL,
  validating_carrier TEXT, mct_status TEXT, requires_entry INTEGER NOT NULL CHECK(requires_entry IN (0,1)),
  requires_bag_reclaim INTEGER NOT NULL CHECK(requires_bag_reclaim IN (0,1)), through_bag_status TEXT,
  terminal_change INTEGER NOT NULL CHECK(terminal_change IN (0,1)), airport_change INTEGER NOT NULL CHECK(airport_change IN (0,1)),
  scheduled_buffer_minutes INTEGER NOT NULL CHECK(scheduled_buffer_minutes >= 0), required_buffer_minutes INTEGER NOT NULL CHECK(required_buffer_minutes >= 0),
  buffer_confidence TEXT NOT NULL, reaccommodation_basis TEXT, evidence_id TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS cost_components (
  cost_id TEXT PRIMARY KEY, itinerary_id TEXT NOT NULL REFERENCES itinerary_candidates(itinerary_id) ON DELETE CASCADE,
  type TEXT NOT NULL, amount REAL NOT NULL CHECK(amount >= 0), currency TEXT NOT NULL, twd_amount REAL,
  inclusion_state TEXT NOT NULL CHECK(inclusion_state IN ('INCLUDED_IN_OFFER','ADD_ON','UNKNOWN')),
  source_offer_id TEXT, dedupe_key TEXT NOT NULL, certainty TEXT NOT NULL, effective_event_at TEXT, paid_state TEXT NOT NULL,
  refundable INTEGER NOT NULL CHECK(refundable IN (0,1)), fx_snapshot_id TEXT, observed_at TEXT NOT NULL,
  UNIQUE(itinerary_id, dedupe_key)
);
CREATE TABLE IF NOT EXISTS readiness_facets (
  itinerary_id TEXT NOT NULL REFERENCES itinerary_candidates(itinerary_id) ON DELETE CASCADE,
  facet_type TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('PASS','FAIL','UNKNOWN','STALE')),
  reason_code TEXT NOT NULL, observed_at TEXT NOT NULL, expires_at TEXT NOT NULL, authority TEXT NOT NULL, evidence_id TEXT NOT NULL,
  PRIMARY KEY(itinerary_id, facet_type)
);
CREATE TABLE IF NOT EXISTS document_requirements (
  document_id TEXT PRIMARY KEY, itinerary_id TEXT NOT NULL REFERENCES itinerary_candidates(itinerary_id) ON DELETE CASCADE,
  jurisdiction TEXT NOT NULL, travel_event TEXT NOT NULL, traveler_document_class TEXT NOT NULL, status TEXT NOT NULL,
  announced_at TEXT, observed_at TEXT NOT NULL, effective_from TEXT, effective_to TEXT, valid_for_event_at TEXT NOT NULL,
  jurisdiction_timezone TEXT NOT NULL, authority_source TEXT NOT NULL, source_snapshot_id TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS four_leg_liabilities (
  liability_id TEXT PRIMARY KEY, itinerary_id TEXT NOT NULL REFERENCES itinerary_candidates(itinerary_id) ON DELETE CASCADE,
  cycle_id TEXT NOT NULL, component_type TEXT NOT NULL CHECK(component_type IN ('POSITIONING','MAIN_TICKET','TAIL_RETURN','HOTEL','DOCUMENT')),
  amount REAL NOT NULL CHECK(amount >= 0), paid_state TEXT NOT NULL, refundable INTEGER NOT NULL CHECK(refundable IN (0,1)),
  booking_deadline TEXT, travel_deadline TEXT, remaining_exposure REAL NOT NULL CHECK(remaining_exposure >= 0),
  recoverable_amount REAL NOT NULL CHECK(recoverable_amount >= 0)
);
CREATE TABLE IF NOT EXISTS audit_evidence (
  evidence_id TEXT PRIMARY KEY, gate_id TEXT NOT NULL, spec_version TEXT NOT NULL, commit_sha TEXT,
  dependency_lock_hash TEXT, build_run_id TEXT, deployed_version TEXT, test_report_hash TEXT,
  provider_readback TEXT, unresolved_items TEXT, created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_ticket_itinerary ON ticket_components(itinerary_id);
CREATE INDEX IF NOT EXISTS idx_transfer_itinerary ON transfer_boundaries(itinerary_id);
CREATE INDEX IF NOT EXISTS idx_cost_itinerary ON cost_components(itinerary_id);
CREATE INDEX IF NOT EXISTS idx_document_itinerary ON document_requirements(itinerary_id);
CREATE INDEX IF NOT EXISTS idx_liability_itinerary ON four_leg_liabilities(itinerary_id);
