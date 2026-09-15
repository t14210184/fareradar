CREATE TABLE IF NOT EXISTS candidate_priority_queue (
  queue_id TEXT PRIMARY KEY,
  signal_type TEXT NOT NULL CHECK(signal_type IN ('PROMOTION','AGENCY_CLEARANCE')),
  signal_id TEXT NOT NULL,
  required_verification TEXT NOT NULL CHECK(required_verification IN ('LIVE_REPRICE','SELLER_RECHECK')),
  priority_score REAL NOT NULL CHECK(priority_score >= 0 AND priority_score <= 100),
  route_scope_json TEXT NOT NULL,
  price_claim_json TEXT,
  source_evidence_id TEXT NOT NULL,
  state TEXT NOT NULL DEFAULT 'PENDING' CHECK(state IN ('PENDING','LEASED','DONE','DEAD')),
  attempts INTEGER NOT NULL DEFAULT 0,
  available_at TEXT NOT NULL,
  lease_until TEXT,
  claimed_by TEXT,
  last_error TEXT,
  first_observed_at TEXT NOT NULL,
  last_observed_at TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(signal_type, signal_id)
);
CREATE INDEX IF NOT EXISTS idx_candidate_priority_claim
  ON candidate_priority_queue(state, available_at, priority_score DESC, first_observed_at ASC);
