CREATE TABLE IF NOT EXISTS shadow_review_samples (
  sample_id TEXT PRIMARY KEY,
  subject_type TEXT NOT NULL CHECK(subject_type IN ('ITINERARY','PROMOTION','AGENCY_OFFER','SOURCE_EVENT','EMAIL','ROUTE')),
  subject_id TEXT NOT NULL,
  evidence_id TEXT NOT NULL,
  observed_at TEXT NOT NULL,
  label TEXT NOT NULL,
  complex INTEGER NOT NULL CHECK(complex IN (0,1)),
  source_discovery INTEGER NOT NULL CHECK(source_discovery IN (0,1)),
  agency_clearance INTEGER NOT NULL CHECK(agency_clearance IN (0,1)),
  false_actionable INTEGER NOT NULL CHECK(false_actionable IN (0,1)),
  safety_error_code TEXT,
  strategy_type TEXT,
  reviewer_key_id TEXT NOT NULL,
  review_payload_sha256 TEXT NOT NULL,
  commit_sha TEXT NOT NULL,
  created_at TEXT NOT NULL,
  UNIQUE(subject_type,subject_id,evidence_id)
);
CREATE INDEX IF NOT EXISTS idx_shadow_review_commit_created ON shadow_review_samples(commit_sha,created_at);
CREATE INDEX IF NOT EXISTS idx_shadow_review_commit_subject ON shadow_review_samples(commit_sha,subject_type);
