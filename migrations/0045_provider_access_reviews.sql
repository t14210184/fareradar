CREATE TABLE IF NOT EXISTS provider_access_reviews (
  review_id TEXT PRIMARY KEY,
  provider_id TEXT NOT NULL REFERENCES provider_access_registry(provider_id) ON DELETE CASCADE,
  access_basis TEXT NOT NULL,
  terms_snapshot_at TEXT NOT NULL,
  rate_policy TEXT NOT NULL,
  look_to_book_budget INTEGER,
  evidence_id TEXT NOT NULL REFERENCES audit_evidence(evidence_id),
  reviewer_key_id TEXT NOT NULL,
  human_review_sha256 TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_provider_access_review_provider_created ON provider_access_reviews(provider_id,created_at);
CREATE INDEX IF NOT EXISTS idx_provider_access_review_reviewer ON provider_access_reviews(reviewer_key_id,provider_id,created_at);
