PRAGMA foreign_keys=ON;

ALTER TABLE ingest_auth_keys ADD COLUMN provider_id TEXT REFERENCES provider_access_registry(provider_id);
CREATE INDEX IF NOT EXISTS idx_ingest_auth_provider ON ingest_auth_keys(provider_id,enabled,expires_at);
