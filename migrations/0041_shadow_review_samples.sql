CREATE TABLE IF NOT EXISTS shadow_review_samples (
  sample_id TEXT PRIMARY KEY,
  subject_type TEXT NOT NULL,
  subject_id TEXT NOT NULL,
  evidence_id TEXT NOT NULL,
  observed_at TEXT NOT NULL,
  strategy_type TEXT,
  actionable INTEGER NOT NULL CHECK(actionable IN (0,1)),
  safety_critical INTEGER NOT NULL DEFAULT 0 CHECK(safety_critical IN (0,1)),
  reviewer_key_id TEXT NOT NULL,
  review_payload_sha256 TEXT NOT NULL,
  commit_sha TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_shadow_review_commit_created ON shadow_review_samples(commit_sha,created_at);
