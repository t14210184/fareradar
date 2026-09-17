CREATE TABLE IF NOT EXISTS candidate_offer_links (
  queue_id TEXT NOT NULL REFERENCES candidate_priority_queue(queue_id) ON DELETE CASCADE,
  plan_id TEXT NOT NULL REFERENCES provider_search_plans(plan_id) ON DELETE CASCADE,
  job_id TEXT NOT NULL REFERENCES verification_jobs(job_id) ON DELETE CASCADE,
  provider_offer_id TEXT NOT NULL REFERENCES offer_snapshots(provider_offer_id) ON DELETE CASCADE,
  query_fingerprint TEXT NOT NULL,
  created_at TEXT NOT NULL,
  PRIMARY KEY(queue_id, provider_offer_id)
);
CREATE INDEX IF NOT EXISTS idx_candidate_offer_query ON candidate_offer_links(queue_id,query_fingerprint,job_id);

CREATE TABLE IF NOT EXISTS candidate_verification_results (
  result_id TEXT PRIMARY KEY,
  queue_id TEXT NOT NULL REFERENCES candidate_priority_queue(queue_id) ON DELETE CASCADE,
  query_fingerprint TEXT NOT NULL,
  verification_state TEXT NOT NULL CHECK(verification_state IN ('PROBABLE','CONFIRMED')),
  reason TEXT NOT NULL,
  best_offer_id TEXT REFERENCES offer_snapshots(provider_offer_id),
  best_offer_total REAL,
  currency TEXT,
  live_offer_count INTEGER NOT NULL,
  provider_count INTEGER NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(queue_id, query_fingerprint)
);
CREATE INDEX IF NOT EXISTS idx_candidate_verification_state ON candidate_verification_results(verification_state,updated_at);
