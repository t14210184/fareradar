CREATE TABLE IF NOT EXISTS search_campaigns (
  campaign_id TEXT PRIMARY KEY,
  profile_id TEXT NOT NULL,
  provider_id TEXT NOT NULL REFERENCES provider_access_registry(provider_id),
  origin_airports_json TEXT NOT NULL,
  destination_airports_json TEXT NOT NULL,
  departure_dates_json TEXT NOT NULL,
  trip_lengths_json TEXT NOT NULL,
  passengers_json TEXT NOT NULL,
  cabin_class TEXT,
  max_connections INTEGER CHECK(max_connections IS NULL OR (max_connections>=0 AND max_connections<=3)),
  market TEXT,
  locale TEXT,
  max_queries_per_signal INTEGER NOT NULL CHECK(max_queries_per_signal>=1 AND max_queries_per_signal<=8),
  enabled INTEGER NOT NULL CHECK(enabled IN (0,1)),
  expires_at TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_search_campaign_active ON search_campaigns(enabled,expires_at,updated_at);

CREATE TABLE IF NOT EXISTS provider_search_plans (
  plan_id TEXT PRIMARY KEY,
  campaign_id TEXT NOT NULL REFERENCES search_campaigns(campaign_id) ON DELETE CASCADE,
  queue_id TEXT NOT NULL REFERENCES candidate_priority_queue(queue_id) ON DELETE CASCADE,
  provider_id TEXT NOT NULL REFERENCES provider_access_registry(provider_id),
  query_fingerprint TEXT NOT NULL,
  query_json TEXT NOT NULL,
  state TEXT NOT NULL DEFAULT 'READY' CHECK(state IN ('READY','DISPATCHED','DEAD')),
  provider_job_id TEXT,
  attempts INTEGER NOT NULL DEFAULT 0,
  next_attempt_at TEXT NOT NULL,
  last_error TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(campaign_id,queue_id,query_fingerprint)
);
CREATE INDEX IF NOT EXISTS idx_provider_search_plan_dispatch ON provider_search_plans(state,next_attempt_at,created_at);

CREATE TABLE IF NOT EXISTS provider_job_consumers (
  job_id TEXT NOT NULL REFERENCES verification_jobs(job_id) ON DELETE CASCADE,
  plan_id TEXT NOT NULL REFERENCES provider_search_plans(plan_id) ON DELETE CASCADE,
  queue_id TEXT NOT NULL REFERENCES candidate_priority_queue(queue_id) ON DELETE CASCADE,
  created_at TEXT NOT NULL,
  PRIMARY KEY(job_id,plan_id)
);
CREATE INDEX IF NOT EXISTS idx_provider_job_consumer_queue ON provider_job_consumers(queue_id,job_id);
