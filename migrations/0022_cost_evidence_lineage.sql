PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS cost_evidence_snapshots (
  evidence_id TEXT PRIMARY KEY,
  evidence_type TEXT NOT NULL,
  subject_key TEXT NOT NULL,
  amount REAL NOT NULL CHECK(amount >= 0),
  currency TEXT NOT NULL,
  source_id TEXT REFERENCES source_registry(source_id),
  source_observation_id TEXT REFERENCES source_observations(observation_id),
  canonical_url TEXT,
  authority TEXT NOT NULL,
  access_basis TEXT NOT NULL,
  effective_event_at TEXT,
  observed_at TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  raw_sha256 TEXT NOT NULL,
  privacy_class TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  CHECK(source_id IS NOT NULL OR source_observation_id IS NOT NULL OR access_basis IN ('PRIVATE_RUNTIME','PARTNER_PUSH'))
);
CREATE INDEX IF NOT EXISTS idx_cost_evidence_type_subject ON cost_evidence_snapshots(evidence_type,subject_key,observed_at);

ALTER TABLE fx_snapshots ADD COLUMN source_id TEXT REFERENCES source_registry(source_id);
ALTER TABLE fx_snapshots ADD COLUMN canonical_url TEXT;
ALTER TABLE fx_snapshots ADD COLUMN authority TEXT;
