PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS runtime_entitlements (
  entitlement_id TEXT PRIMARY KEY,
  profile_id TEXT NOT NULL REFERENCES runtime_profiles(profile_id) ON DELETE CASCADE,
  entitlement_type TEXT NOT NULL CHECK(entitlement_type IN ('MEMBER','SUBSCRIPTION','CHANNEL')),
  entitlement_key TEXT NOT NULL,
  state TEXT NOT NULL CHECK(state IN ('ACTIVE','INACTIVE')),
  valid_from TEXT,
  valid_to TEXT,
  evidence_sha256 TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(profile_id,entitlement_type,entitlement_key)
);
CREATE INDEX IF NOT EXISTS idx_runtime_entitlements_active ON runtime_entitlements(profile_id,state,valid_to,entitlement_type,entitlement_key);
