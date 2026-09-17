CREATE TABLE IF NOT EXISTS agency_inventory_offers (
  agency_offer_id TEXT PRIMARY KEY, agency_id TEXT NOT NULL REFERENCES agency_partner_registry(agency_id),
  seller_verification_state TEXT NOT NULL, product_id TEXT NOT NULL, allotment_type TEXT NOT NULL,
  origin TEXT NOT NULL, destination TEXT NOT NULL, flight_number TEXT, departure_at TEXT NOT NULL, return_at TEXT,
  price REAL NOT NULL CHECK(price >= 0), currency TEXT NOT NULL, tax_inclusion TEXT NOT NULL, baggage TEXT,
  seats_total INTEGER, seats_available INTEGER, inventory_hint TEXT, minimum_group_size INTEGER,
  booking_deadline TEXT, ticketing_deadline TEXT, refund_change_terms TEXT, booking_or_contact_channel TEXT NOT NULL,
  observed_at TEXT NOT NULL, source_evidence_id TEXT NOT NULL REFERENCES source_observations(observation_id), state TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS email_evidence (
  message_id TEXT PRIMARY KEY, source_id TEXT NOT NULL REFERENCES source_registry(source_id), observation_id TEXT NOT NULL REFERENCES source_observations(observation_id),
  from_address TEXT NOT NULL, from_domain TEXT NOT NULL, received_at TEXT NOT NULL, subject TEXT NOT NULL,
  body_sha256 TEXT NOT NULL, attachment_sha256_json TEXT NOT NULL, dkim_result TEXT NOT NULL, spf_result TEXT NOT NULL, dmarc_result TEXT NOT NULL,
  canonical_links_json TEXT NOT NULL, expanded_links_json TEXT NOT NULL, link_risk_class TEXT NOT NULL, trust_class TEXT NOT NULL,
  retention_until TEXT NOT NULL
);
