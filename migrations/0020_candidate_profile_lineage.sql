ALTER TABLE itinerary_candidates ADD COLUMN profile_id TEXT REFERENCES runtime_profiles(profile_id);
CREATE INDEX IF NOT EXISTS idx_itinerary_profile ON itinerary_candidates(profile_id,updated_at);
