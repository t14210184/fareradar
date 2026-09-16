ALTER TABLE audit_evidence ADD COLUMN entity_type TEXT;
ALTER TABLE audit_evidence ADD COLUMN entity_id TEXT;
ALTER TABLE audit_evidence ADD COLUMN review_id TEXT;
ALTER TABLE audit_evidence ADD COLUMN reviewer_key_id TEXT;
CREATE INDEX IF NOT EXISTS idx_audit_review_binding ON audit_evidence(entity_type,entity_id,review_id);
