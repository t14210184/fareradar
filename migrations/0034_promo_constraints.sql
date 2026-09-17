PRAGMA foreign_keys=ON;
ALTER TABLE promotion_events ADD COLUMN constraint_json TEXT NOT NULL DEFAULT '{}';
