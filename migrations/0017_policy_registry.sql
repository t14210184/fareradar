CREATE TABLE IF NOT EXISTS policy_records (
  policy_record_id TEXT PRIMARY KEY,
  policy_code TEXT NOT NULL,
  jurisdiction TEXT NOT NULL,
  traveler_document_class TEXT NOT NULL,
  announced_at TEXT,
  observed_at TEXT NOT NULL,
  effective_from TEXT,
  effective_to TEXT,
  jurisdiction_timezone TEXT NOT NULL,
  travel_event TEXT NOT NULL,
  ticket_issue_rule TEXT,
  source_url TEXT NOT NULL,
  source_authority TEXT NOT NULL,
  source_snapshot_hash TEXT NOT NULL,
  refresh_margin_hours INTEGER NOT NULL DEFAULT 24 CHECK(refresh_margin_hours >= 0),
  ttl_hours INTEGER NOT NULL CHECK(ttl_hours > 0),
  watch_window_hours INTEGER CHECK(watch_window_hours IS NULL OR watch_window_hours >= 0),
  decision_status TEXT NOT NULL CHECK(decision_status IN ('CLEAR','REQUIRES_DOCUMENT','BLOCKED','RECHECK_REQUIRED')),
  status TEXT NOT NULL CHECK(status IN ('CURRENT','RECHECK_REQUIRED','STALE')),
  created_at TEXT NOT NULL,
  UNIQUE(policy_code, source_snapshot_hash)
);
CREATE INDEX IF NOT EXISTS idx_policy_lookup
  ON policy_records(policy_code, traveler_document_class, observed_at DESC);
