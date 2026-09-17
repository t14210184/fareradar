CREATE TABLE IF NOT EXISTS source_outcome_attributions (
  attribution_id TEXT PRIMARY KEY,
  itinerary_id TEXT NOT NULL REFERENCES itinerary_candidates(itinerary_id) ON DELETE CASCADE,
  source_id TEXT NOT NULL REFERENCES source_registry(source_id) ON DELETE CASCADE,
  observation_id TEXT NOT NULL REFERENCES source_observations(observation_id),
  outcome_type TEXT NOT NULL CHECK(outcome_type IN ('CONFIRMED')),
  first_win INTEGER NOT NULL CHECK(first_win IN (0,1)),
  window_date TEXT NOT NULL,
  observed_at TEXT NOT NULL,
  confirmed_at TEXT NOT NULL,
  UNIQUE(itinerary_id, source_id, outcome_type)
);
CREATE INDEX IF NOT EXISTS idx_source_outcome_source_date ON source_outcome_attributions(source_id,window_date,outcome_type);
CREATE TRIGGER IF NOT EXISTS trg_source_outcome_health
AFTER INSERT ON source_outcome_attributions
BEGIN
  INSERT INTO source_health_windows(source_id,window_date,confirmed_count,first_win_count,schedule_action,updated_at)
  VALUES(NEW.source_id,NEW.window_date,1,NEW.first_win,'KEEP',NEW.confirmed_at)
  ON CONFLICT(source_id,window_date) DO UPDATE SET
    confirmed_count=source_health_windows.confirmed_count+1,
    first_win_count=source_health_windows.first_win_count+NEW.first_win,
    updated_at=NEW.confirmed_at;
END;
