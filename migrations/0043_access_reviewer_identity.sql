ALTER TABLE source_onboarding_reviews ADD COLUMN reviewer_key_id TEXT;
ALTER TABLE source_onboarding_reviews ADD COLUMN human_review_sha256 TEXT;
CREATE INDEX IF NOT EXISTS idx_source_onboarding_reviewer ON source_onboarding_reviews(reviewer_key_id,source_id,created_at);
