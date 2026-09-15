CREATE TABLE IF NOT EXISTS source_onboarding_reviews (
  review_id TEXT PRIMARY KEY,
  source_id TEXT NOT NULL REFERENCES source_registry(source_id) ON DELETE CASCADE,
  target_state TEXT NOT NULL CHECK(target_state IN ('SHADOW','ENABLED')),
  terms_snapshot_at TEXT NOT NULL,
  evidence_id TEXT NOT NULL REFERENCES audit_evidence(evidence_id),
  checks_json TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_source_onboarding_source_created ON source_onboarding_reviews(source_id,created_at);
