CREATE TABLE IF NOT EXISTS candidate_verification_supports (
  result_id TEXT NOT NULL REFERENCES candidate_verification_results(result_id) ON DELETE CASCADE,
  provider_offer_id TEXT NOT NULL REFERENCES offer_snapshots(provider_offer_id) ON DELETE CASCADE,
  support_role TEXT NOT NULL CHECK(support_role IN ('PRIMARY','SUPPORT')),
  created_at TEXT NOT NULL,
  PRIMARY KEY(result_id,provider_offer_id)
);
CREATE INDEX IF NOT EXISTS idx_candidate_verification_support_offer
  ON candidate_verification_supports(provider_offer_id,result_id);

CREATE TABLE IF NOT EXISTS live_offer_lifecycle_events (
  event_id TEXT PRIMARY KEY,
  result_id TEXT NOT NULL REFERENCES candidate_verification_results(result_id) ON DELETE CASCADE,
  queue_id TEXT NOT NULL,
  query_fingerprint TEXT NOT NULL,
  itinerary_id TEXT,
  provider_offer_id TEXT NOT NULL REFERENCES offer_snapshots(provider_offer_id),
  previous_verification_state TEXT NOT NULL,
  new_verification_state TEXT NOT NULL,
  reason TEXT NOT NULL CHECK(reason IN ('LIVE_OFFER_EXPIRED')),
  effective_at TEXT NOT NULL,
  support_provider_ids_json TEXT NOT NULL,
  had_visible_notification INTEGER NOT NULL DEFAULT 0 CHECK(had_visible_notification IN (0,1)),
  correction_state TEXT NOT NULL DEFAULT 'PENDING' CHECK(correction_state IN ('PENDING','NOT_REQUIRED','ENQUEUED')),
  reprice_state TEXT NOT NULL DEFAULT 'PENDING' CHECK(reprice_state IN ('PENDING','NOT_REQUIRED','ENQUEUED','PARTIAL','FAILED')),
  last_error TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(result_id,provider_offer_id)
);
CREATE INDEX IF NOT EXISTS idx_live_offer_lifecycle_pending
  ON live_offer_lifecycle_events(correction_state,reprice_state,created_at);
CREATE INDEX IF NOT EXISTS idx_offer_snapshots_live_expiry
  ON offer_snapshots(cached_or_live,expires_at,provider_offer_id);
