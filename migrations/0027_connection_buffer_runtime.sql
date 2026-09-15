PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS connection_buffer_policies (
  policy_id TEXT PRIMARY KEY,
  airport TEXT NOT NULL,
  airport_base_buffer INTEGER NOT NULL CHECK(airport_base_buffer >= 0),
  immigration_margin INTEGER NOT NULL CHECK(immigration_margin >= 0),
  baggage_reclaim_margin INTEGER NOT NULL CHECK(baggage_reclaim_margin >= 0),
  terminal_transfer_margin INTEGER NOT NULL CHECK(terminal_transfer_margin >= 0),
  checkin_cutoff_margin INTEGER NOT NULL CHECK(checkin_cutoff_margin >= 0),
  security_margin INTEGER NOT NULL CHECK(security_margin >= 0),
  delay_margin INTEGER NOT NULL CHECK(delay_margin >= 0),
  buffer_confidence TEXT NOT NULL CHECK(buffer_confidence IN ('LOW','MEDIUM','HIGH')),
  authority TEXT NOT NULL,
  observed_at TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  raw_sha256 TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_connection_buffer_airport ON connection_buffer_policies(airport,observed_at DESC);

ALTER TABLE transfer_boundaries ADD COLUMN evaluation_status TEXT CHECK(evaluation_status IS NULL OR evaluation_status IN ('PASS','FAIL','UNKNOWN','STALE'));
ALTER TABLE transfer_boundaries ADD COLUMN evaluation_reason TEXT;
ALTER TABLE transfer_boundaries ADD COLUMN evaluated_at TEXT;
ALTER TABLE transfer_boundaries ADD COLUMN evaluation_expires_at TEXT;
