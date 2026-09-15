CREATE TABLE IF NOT EXISTS runtime_payment_profiles (
  payment_profile_id TEXT PRIMARY KEY,
  provider_id TEXT NOT NULL REFERENCES provider_access_registry(provider_id) ON DELETE CASCADE,
  payment_method_class TEXT NOT NULL CHECK(payment_method_class IN ('CARD')),
  credential_binding TEXT NOT NULL,
  enabled INTEGER NOT NULL DEFAULT 1 CHECK(enabled IN (0,1)),
  expires_at TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_runtime_payment_profile_provider ON runtime_payment_profiles(provider_id,enabled,expires_at);

CREATE TABLE IF NOT EXISTS provider_pricing_quotes (
  quote_id TEXT PRIMARY KEY,
  provider_offer_id TEXT NOT NULL REFERENCES offer_snapshots(provider_offer_id) ON DELETE CASCADE,
  provider_id TEXT NOT NULL REFERENCES provider_access_registry(provider_id) ON DELETE CASCADE,
  source_job_id TEXT,
  payment_profile_id TEXT NOT NULL REFERENCES runtime_payment_profiles(payment_profile_id),
  selected_services_json TEXT NOT NULL,
  payment_method_class TEXT NOT NULL CHECK(payment_method_class IN ('CARD')),
  currency TEXT NOT NULL,
  fare_and_services_total REAL NOT NULL CHECK(fare_and_services_total >= 0),
  surcharge_total REAL NOT NULL CHECK(surcharge_total >= 0),
  grand_total REAL NOT NULL CHECK(grand_total >= 0),
  priced_at TEXT NOT NULL,
  expires_at TEXT,
  raw_sha256 TEXT NOT NULL,
  price_scope TEXT NOT NULL CHECK(price_scope='CHECKOUT_TOTAL_WITH_SELECTED_SERVICES_AND_PAYMENT_SURCHARGE'),
  UNIQUE(provider_offer_id,payment_profile_id,selected_services_json,raw_sha256)
);
CREATE INDEX IF NOT EXISTS idx_pricing_quote_offer_time ON provider_pricing_quotes(provider_offer_id,priced_at);
ALTER TABLE cost_components ADD COLUMN pricing_quote_id TEXT REFERENCES provider_pricing_quotes(quote_id);
