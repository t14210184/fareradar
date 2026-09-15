PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS cost_coverage_assertions (
  itinerary_id TEXT NOT NULL REFERENCES itinerary_candidates(itinerary_id) ON DELETE CASCADE,
  category TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('COVERED','NOT_APPLICABLE','UNKNOWN')),
  evidence_id TEXT NOT NULL,
  authority TEXT NOT NULL,
  observed_at TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  details_json TEXT NOT NULL,
  PRIMARY KEY(itinerary_id, category)
);
CREATE INDEX IF NOT EXISTS idx_cost_coverage_expiry ON cost_coverage_assertions(expires_at,status);
