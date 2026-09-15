CREATE TABLE IF NOT EXISTS agency_recheck_evidence (
  recheck_id TEXT PRIMARY KEY,
  queue_id TEXT NOT NULL REFERENCES candidate_priority_queue(queue_id) ON DELETE CASCADE,
  agency_offer_id TEXT NOT NULL REFERENCES agency_inventory_offers(agency_offer_id) ON DELETE CASCADE,
  agency_id TEXT NOT NULL REFERENCES agency_partner_registry(agency_id),
  worker_id TEXT NOT NULL,
  readback_basis TEXT NOT NULL CHECK(readback_basis IN ('PARTNER_API','PARTNER_PORTAL','OFFICIAL_PRODUCT_PAGE')),
  source_url TEXT NOT NULL,
  content_sha256 TEXT NOT NULL,
  observed_at TEXT NOT NULL,
  price REAL NOT NULL CHECK(price >= 0),
  currency TEXT NOT NULL,
  seats_available INTEGER CHECK(seats_available IS NULL OR seats_available >= 0),
  booking_deadline TEXT,
  ticketing_deadline TEXT,
  result_state TEXT NOT NULL CHECK(result_state IN ('SELLER_CONFIRMED','SOLD_OUT','RECHECK_REQUIRED')),
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_agency_recheck_offer ON agency_recheck_evidence(agency_offer_id,observed_at);
