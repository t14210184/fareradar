ALTER TABLE notification_outbox ADD COLUMN claimed_by TEXT;
ALTER TABLE notification_outbox ADD COLUMN last_error TEXT;
ALTER TABLE domain_outbox ADD COLUMN claimed_by TEXT;
ALTER TABLE domain_outbox ADD COLUMN last_error TEXT;
