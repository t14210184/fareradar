PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS four_leg_cycles (
  cycle_id TEXT PRIMARY KEY,
  itinerary_id TEXT NOT NULL UNIQUE REFERENCES itinerary_candidates(itinerary_id) ON DELETE CASCADE,
  state TEXT NOT NULL CHECK(state IN ('NOT_STARTED','POSITIONING_BOOKED','AT_EXTERNAL_ORIGIN','LEG1_FLOWN','HOME_STOPOVER','MAIN_TRIP_ACTIVE','LEG3_FLOWN','TAIL_PENDING','CYCLE_COMPLETED','BROKEN')),
  broken_reason TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_four_leg_cycle_state ON four_leg_cycles(state,updated_at);
