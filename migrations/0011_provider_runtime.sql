ALTER TABLE provider_access_registry ADD COLUMN connector_state TEXT NOT NULL DEFAULT 'UNIMPLEMENTED';
ALTER TABLE provider_access_registry ADD COLUMN supported_verification_json TEXT NOT NULL DEFAULT '[]';
ALTER TABLE provider_access_registry ADD COLUMN credential_binding TEXT;
ALTER TABLE provider_access_registry ADD COLUMN background_allowed INTEGER NOT NULL DEFAULT 0 CHECK(background_allowed IN (0,1));

CREATE TABLE IF NOT EXISTS provider_runtime_readbacks (
  provider_id TEXT NOT NULL REFERENCES provider_access_registry(provider_id) ON DELETE CASCADE,
  worker_id TEXT NOT NULL,
  connector_version TEXT NOT NULL,
  credentials_present INTEGER NOT NULL CHECK(credentials_present IN (0,1)),
  capabilities_json TEXT NOT NULL,
  checked_at TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  PRIMARY KEY(provider_id, worker_id)
);
CREATE INDEX IF NOT EXISTS idx_provider_runtime_active ON provider_runtime_readbacks(provider_id,expires_at,credentials_present);
