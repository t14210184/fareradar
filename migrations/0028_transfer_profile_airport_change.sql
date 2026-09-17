PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS airport_change_policies (
  policy_id TEXT PRIMARY KEY,
  from_airport TEXT NOT NULL,
  to_airport TEXT NOT NULL,
  ground_transfer_minutes INTEGER NOT NULL CHECK(ground_transfer_minutes >= 0),
  ground_contingency_minutes INTEGER NOT NULL CHECK(ground_contingency_minutes >= 0),
  authority TEXT NOT NULL,
  observed_at TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  raw_sha256 TEXT NOT NULL,
  created_at TEXT NOT NULL,
  CHECK(length(from_airport)=3),
  CHECK(length(to_airport)=3),
  CHECK(from_airport<>to_airport)
);
CREATE INDEX IF NOT EXISTS idx_airport_change_pair ON airport_change_policies(from_airport,to_airport,observed_at DESC);

ALTER TABLE transfer_boundaries ADD COLUMN arrival_airport TEXT;
ALTER TABLE transfer_boundaries ADD COLUMN departure_airport TEXT;
ALTER TABLE transfer_boundaries ADD COLUMN overnight_transfer INTEGER NOT NULL DEFAULT 0 CHECK(overnight_transfer IN (0,1));
ALTER TABLE transfer_boundaries ADD COLUMN airport_change_policy_id TEXT REFERENCES airport_change_policies(policy_id);
