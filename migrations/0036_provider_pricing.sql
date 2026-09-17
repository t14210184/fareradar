CREATE TABLE IF NOT EXISTS provider_pricing_snapshots (
  pricing_snapshot_id TEXT PRIMARY KEY,
  provider_id TEXT NOT NULL REFERENCES provider_access_registry(provider_id) ON DELETE CASCADE,
  usage_window_kind TEXT NOT NULL CHECK(usage_window_kind IN ('CALENDAR_MONTH','LIFETIME')),
  search_to_book_threshold INTEGER NOT NULL CHECK(search_to_book_threshold > 0),
  hard_search_cap INTEGER CHECK(hard_search_cap IS NULL OR hard_search_cap > 0),
  currency TEXT,
  rate_json TEXT NOT NULL,
  source_url TEXT NOT NULL,
  raw_sha256 TEXT NOT NULL,
  observed_at TEXT NOT NULL,
  effective_from TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  state TEXT NOT NULL CHECK(state IN ('ACTIVE','SUPERSEDED')),
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_provider_pricing_current ON provider_pricing_snapshots(provider_id,state,effective_from,expires_at);

CREATE TABLE IF NOT EXISTS provider_usage_windows (
  provider_id TEXT NOT NULL REFERENCES provider_access_registry(provider_id) ON DELETE CASCADE,
  window_key TEXT NOT NULL,
  pricing_snapshot_id TEXT NOT NULL REFERENCES provider_pricing_snapshots(pricing_snapshot_id),
  search_count INTEGER NOT NULL DEFAULT 0 CHECK(search_count >= 0),
  confirmed_order_count INTEGER NOT NULL DEFAULT 0 CHECK(confirmed_order_count >= 0),
  circuit_state TEXT NOT NULL DEFAULT 'CLEAR' CHECK(circuit_state IN ('CLEAR','OPEN')),
  opened_reason TEXT,
  updated_at TEXT NOT NULL,
  PRIMARY KEY(provider_id,window_key)
);
