PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS fare_baseline_observations (
  baseline_id TEXT PRIMARY KEY,
  provider_offer_id TEXT NOT NULL UNIQUE REFERENCES offer_snapshots(provider_offer_id) ON DELETE CASCADE,
  baseline_key TEXT NOT NULL,
  route_key TEXT NOT NULL,
  metro_pair TEXT NOT NULL,
  direction TEXT NOT NULL,
  trip_type TEXT NOT NULL,
  nonstop_or_stop TEXT NOT NULL,
  protected_or_self_transfer TEXT NOT NULL,
  fare_brand TEXT NOT NULL,
  baggage_profile TEXT NOT NULL,
  weekday INTEGER NOT NULL CHECK(weekday BETWEEN 0 AND 6),
  season TEXT NOT NULL,
  holiday_bucket TEXT NOT NULL,
  advance_purchase_bucket TEXT NOT NULL,
  provider TEXT NOT NULL,
  currency TEXT NOT NULL,
  amount REAL NOT NULL CHECK(amount >= 0),
  departure_date TEXT NOT NULL,
  observed_at TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_fare_baseline_key_time ON fare_baseline_observations(baseline_key,observed_at);
CREATE INDEX IF NOT EXISTS idx_fare_baseline_route_time ON fare_baseline_observations(route_key,observed_at);
