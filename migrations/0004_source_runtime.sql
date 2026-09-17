CREATE TABLE IF NOT EXISTS source_fetch_state (
  source_id TEXT PRIMARY KEY REFERENCES source_registry(source_id) ON DELETE CASCADE,
  last_attempt_at TEXT, last_success_at TEXT, etag TEXT, last_modified TEXT, content_sha256 TEXT,
  consecutive_failures INTEGER NOT NULL DEFAULT 0, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS source_health_windows (
  source_id TEXT NOT NULL REFERENCES source_registry(source_id) ON DELETE CASCADE,
  window_date TEXT NOT NULL, fetch_count INTEGER NOT NULL DEFAULT 0, success_count INTEGER NOT NULL DEFAULT 0,
  duplicate_count INTEGER NOT NULL DEFAULT 0, confirmed_count INTEGER NOT NULL DEFAULT 0, first_win_count INTEGER NOT NULL DEFAULT 0,
  ghost_count INTEGER NOT NULL DEFAULT 0, schema_drift_count INTEGER NOT NULL DEFAULT 0,
  schedule_action TEXT NOT NULL DEFAULT 'KEEP', updated_at TEXT NOT NULL,
  PRIMARY KEY(source_id,window_date)
);
CREATE TABLE IF NOT EXISTS verification_jobs (
  job_id TEXT PRIMARY KEY, job_type TEXT NOT NULL, target_class TEXT NOT NULL, source_id TEXT,
  payload_json TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'PENDING', attempts INTEGER NOT NULL DEFAULT 0,
  available_at TEXT NOT NULL, lease_until TEXT, claimed_by TEXT, last_error TEXT, created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_verification_jobs_claim ON verification_jobs(state,available_at,created_at);
CREATE INDEX IF NOT EXISTS idx_health_source_date ON source_health_windows(source_id,window_date);
