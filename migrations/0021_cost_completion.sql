ALTER TABLE cost_components ADD COLUMN source_evidence_id TEXT;
ALTER TABLE cost_components ADD COLUMN evidence_expires_at TEXT;

CREATE TABLE IF NOT EXISTS fx_snapshots (
  fx_snapshot_id TEXT PRIMARY KEY,
  base_currency TEXT NOT NULL,
  quote_currency TEXT NOT NULL,
  rate REAL NOT NULL CHECK(rate > 0),
  rate_source TEXT NOT NULL,
  rate_observed_at TEXT NOT NULL,
  provider_spread REAL NOT NULL DEFAULT 0 CHECK(provider_spread >= 0),
  card_fx_fee REAL NOT NULL DEFAULT 0 CHECK(card_fx_fee >= 0),
  settlement_currency TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  raw_sha256 TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_fx_pair_time ON fx_snapshots(base_currency,quote_currency,rate_observed_at);
