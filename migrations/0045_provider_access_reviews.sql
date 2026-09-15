PRAGMA foreign_keys=ON;

ALTER TABLE source_onboarding_reviews ADD COLUMN access_basis TEXT;
ALTER TABLE source_onboarding_reviews ADD COLUMN reviewer_key_id TEXT REFERENCES ingest_auth_keys(key_id);
CREATE INDEX IF NOT EXISTS idx_source_onboarding_reviewer ON source_onboarding_reviews(source_id,reviewer_key_id,created_at);

CREATE TABLE IF NOT EXISTS provider_access_reviews (
  review_id TEXT PRIMARY KEY,
  provider_id TEXT NOT NULL REFERENCES provider_access_registry(provider_id) ON DELETE CASCADE,
  access_basis TEXT NOT NULL,
  terms_snapshot_at TEXT NOT NULL,
  rate_policy TEXT NOT NULL,
  evidence_id TEXT NOT NULL REFERENCES audit_evidence(evidence_id),
  checks_json TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL,
  reviewer_key_id TEXT NOT NULL REFERENCES ingest_auth_keys(key_id),
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_provider_access_reviews_provider_created ON provider_access_reviews(provider_id,created_at);
CREATE INDEX IF NOT EXISTS idx_provider_access_reviews_reviewer ON provider_access_reviews(provider_id,reviewer_key_id,created_at);
