PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS carrier_ticketing_policies (
  policy_id TEXT PRIMARY KEY,
  carrier TEXT NOT NULL,
  policy_type TEXT NOT NULL CHECK(policy_type IN ('COUPON_SEQUENCE','BACK_TO_BACK')),
  consequence TEXT NOT NULL CHECK(consequence IN ('ALLOW','COUPON_SEQUENCE_VOID_RISK','COUPON_RECALCULATION_LIABILITY','CARRIER_REFUSAL_RISK','UNKNOWN_POLICY_CONSEQUENCE','BACK_TO_BACK_RESTRICTED')),
  terms_url TEXT NOT NULL,
  article_or_clause TEXT NOT NULL,
  observed_at TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  source_snapshot_hash TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('CURRENT','RECHECK_REQUIRED','STALE')),
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_ticketing_policy_lookup ON carrier_ticketing_policies(carrier,policy_type,observed_at DESC);
