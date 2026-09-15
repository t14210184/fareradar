ALTER TABLE cost_components ADD COLUMN policy_evidence_id TEXT;
CREATE INDEX IF NOT EXISTS idx_offer_itinerary ON offer_snapshots(itinerary_id);
CREATE INDEX IF NOT EXISTS idx_offer_query ON offer_snapshots(query_fingerprint,provider,observed_at);
