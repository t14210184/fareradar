CREATE TABLE IF NOT EXISTS agency_checkout_jobs (
  job_id TEXT PRIMARY KEY,
  agency_offer_id TEXT NOT NULL UNIQUE REFERENCES agency_inventory_offers(agency_offer_id) ON DELETE CASCADE,
  agency_id TEXT NOT NULL REFERENCES agency_partner_registry(agency_id),
  state TEXT NOT NULL CHECK(state IN ('PENDING','LEASED','DONE','DEAD')),
  attempts INTEGER NOT NULL DEFAULT 0 CHECK(attempts >= 0),
  available_at TEXT NOT NULL,
  claimed_by TEXT,
  lease_until TEXT,
  last_error TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_agency_checkout_due ON agency_checkout_jobs(agency_id,state,available_at);

CREATE TABLE IF NOT EXISTS agency_checkout_evidence (
  checkout_id TEXT PRIMARY KEY,
  job_id TEXT NOT NULL REFERENCES agency_checkout_jobs(job_id) ON DELETE CASCADE,
  agency_offer_id TEXT NOT NULL REFERENCES agency_inventory_offers(agency_offer_id) ON DELETE CASCADE,
  agency_id TEXT NOT NULL REFERENCES agency_partner_registry(agency_id),
  worker_id TEXT NOT NULL,
  readback_basis TEXT NOT NULL CHECK(readback_basis IN ('PARTNER_BOOKING_API','PARTNER_PORTAL_CHECKOUT','OFFICIAL_CHECKOUT_PAGE')),
  checkout_url TEXT NOT NULL,
  content_sha256 TEXT NOT NULL,
  observed_at TEXT NOT NULL,
  final_price REAL NOT NULL CHECK(final_price >= 0),
  currency TEXT NOT NULL,
  seats_available INTEGER CHECK(seats_available IS NULL OR seats_available >= 0),
  booking_deadline TEXT,
  total_includes_taxes INTEGER NOT NULL CHECK(total_includes_taxes IN (0,1)),
  total_includes_mandatory_fees INTEGER NOT NULL CHECK(total_includes_mandatory_fees IN (0,1)),
  payment_dispatched INTEGER NOT NULL DEFAULT 0 CHECK(payment_dispatched=0),
  result_state TEXT NOT NULL CHECK(result_state IN ('CHECKOUT_REPRODUCED','SOLD_OUT','RECHECK_REQUIRED')),
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_agency_checkout_evidence_offer ON agency_checkout_evidence(agency_offer_id,observed_at);
