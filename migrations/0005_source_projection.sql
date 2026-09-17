CREATE TABLE IF NOT EXISTS promotion_events (
  event_id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL UNIQUE, state TEXT NOT NULL CHECK(state IN ('DISCOVERED','WITHDRAWN','EXPIRED')),
  market TEXT, airline TEXT, routes_json TEXT NOT NULL, prices_json TEXT, promo_code TEXT, observed_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS promotion_event_evidence (
  event_id TEXT NOT NULL REFERENCES promotion_events(event_id) ON DELETE CASCADE,
  observation_id TEXT NOT NULL REFERENCES source_observations(observation_id) ON DELETE CASCADE,
  PRIMARY KEY(event_id,observation_id)
);
CREATE TABLE IF NOT EXISTS route_universe (
  route_key TEXT PRIMARY KEY, origin TEXT NOT NULL, destination TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'DISCOVERED',
  source_observation_id TEXT NOT NULL REFERENCES source_observations(observation_id), observed_at TEXT NOT NULL
);
