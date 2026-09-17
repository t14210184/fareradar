ALTER TABLE verification_jobs ADD COLUMN provider_id TEXT REFERENCES provider_access_registry(provider_id);
ALTER TABLE verification_jobs ADD COLUMN query_fingerprint TEXT;
ALTER TABLE verification_jobs ADD COLUMN provider_mode TEXT CHECK(provider_mode IN ('BACKGROUND','USER_REQUEST') OR provider_mode IS NULL);
CREATE INDEX IF NOT EXISTS idx_verification_provider_claim ON verification_jobs(provider_id,target_class,provider_mode,state,available_at,created_at);
