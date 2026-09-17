PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS ingest_auth_keys (
  key_id TEXT PRIMARY KEY,
  role TEXT NOT NULL,
  source_id TEXT,
  agency_id TEXT,
  secret_slot TEXT NOT NULL,
  allowed_paths_json TEXT NOT NULL,
  enabled INTEGER NOT NULL DEFAULT 1 CHECK(enabled IN (0,1)),
  not_before TEXT,
  expires_at TEXT,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_ingest_auth_enabled ON ingest_auth_keys(enabled,expires_at);

CREATE TABLE IF NOT EXISTS used_request_nonces (
  key_id TEXT NOT NULL REFERENCES ingest_auth_keys(key_id) ON DELETE CASCADE,
  nonce TEXT NOT NULL,
  request_sha256 TEXT NOT NULL,
  used_at TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  PRIMARY KEY(key_id,nonce)
);
CREATE INDEX IF NOT EXISTS idx_used_request_nonces_expiry ON used_request_nonces(expires_at);
