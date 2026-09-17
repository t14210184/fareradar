ALTER TABLE agency_inventory_offers ADD COLUMN payment_deadline TEXT;
ALTER TABLE agency_inventory_offers ADD COLUMN expired_at TEXT;
ALTER TABLE agency_inventory_offers ADD COLUMN expiry_reason TEXT;
ALTER TABLE agency_recheck_evidence ADD COLUMN payment_deadline TEXT;
ALTER TABLE agency_checkout_evidence ADD COLUMN payment_deadline TEXT;

CREATE TABLE IF NOT EXISTS agency_offer_lifecycle_events (
  event_id TEXT PRIMARY KEY,
  agency_offer_id TEXT NOT NULL REFERENCES agency_inventory_offers(agency_offer_id) ON DELETE CASCADE,
  previous_state TEXT NOT NULL,
  new_state TEXT NOT NULL CHECK(new_state IN ('EXPIRED','SOLD_OUT')),
  reason TEXT NOT NULL CHECK(reason IN ('BOOKING_DEADLINE_PASSED','PAYMENT_DEADLINE_PASSED','TICKETING_DEADLINE_PASSED','SEATS_EXHAUSTED')),
  effective_at TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_agency_offer_expiry_due ON agency_inventory_offers(state,booking_deadline,payment_deadline,ticketing_deadline,seats_available);
CREATE INDEX IF NOT EXISTS idx_agency_offer_lifecycle_offer ON agency_offer_lifecycle_events(agency_offer_id,created_at);
