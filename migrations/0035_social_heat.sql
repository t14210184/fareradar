CREATE TABLE IF NOT EXISTS promotion_social_heat (
  event_id TEXT PRIMARY KEY REFERENCES promotion_events(event_id) ON DELETE CASCADE,
  window_start TEXT NOT NULL,
  window_end TEXT NOT NULL,
  independent_source_count INTEGER NOT NULL DEFAULT 0,
  high_trust_source_count INTEGER NOT NULL DEFAULT 0,
  source_ids_json TEXT NOT NULL,
  independence_keys_json TEXT NOT NULL,
  heat_score REAL NOT NULL DEFAULT 0,
  route_relevant INTEGER NOT NULL DEFAULT 0 CHECK(route_relevant IN (0,1)),
  provisional_triggered_at TEXT,
  last_evaluated_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_promotion_social_heat_trigger
  ON promotion_social_heat(provisional_triggered_at,last_evaluated_at);
