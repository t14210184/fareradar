CREATE TABLE IF NOT EXISTS runtime_profiles (
  profile_id TEXT PRIMARY KEY,
  home_city TEXT,
  home_airports_json TEXT NOT NULL,
  checked_bag_pattern TEXT NOT NULL CHECK(checked_bag_pattern IN ('NONE','OUTBOUND_ONLY','RETURN_ONLY','BOTH')),
  baggage_kg INTEGER NOT NULL CHECK(baggage_kg >= 0 AND baggage_kg <= 50),
  seat_required INTEGER NOT NULL CHECK(seat_required IN (0,1)),
  red_eye_ok INTEGER NOT NULL CHECK(red_eye_ok IN (0,1)),
  self_transfer_ok INTEGER NOT NULL CHECK(self_transfer_ok IN (0,1)),
  overnight_transfer_ok INTEGER NOT NULL CHECK(overnight_transfer_ok IN (0,1)),
  airport_change_ok INTEGER NOT NULL CHECK(airport_change_ok IN (0,1)),
  mainland_permit_status TEXT NOT NULL,
  korea_entry_profile TEXT NOT NULL,
  foreign_origin_ok INTEGER NOT NULL CHECK(foreign_origin_ok IN (0,1)),
  positioning_cost_attribution TEXT NOT NULL CHECK(positioning_cost_attribution IN ('FULL','MARGINAL','NONE')),
  max_positioning_cost_twd REAL NOT NULL CHECK(max_positioning_cost_twd >= 0),
  value_of_time_twd_per_hour REAL NOT NULL CHECK(value_of_time_twd_per_hour >= 0),
  min_savings_for_self_transfer_twd REAL NOT NULL CHECK(min_savings_for_self_transfer_twd >= 0),
  currency TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_runtime_profiles_updated ON runtime_profiles(updated_at);
