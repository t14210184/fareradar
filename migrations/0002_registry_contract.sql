ALTER TABLE source_registry ADD COLUMN market TEXT;
ALTER TABLE source_registry ADD COLUMN language TEXT;
ALTER TABLE source_registry ADD COLUMN currency TEXT;
ALTER TABLE source_registry ADD COLUMN storage_policy TEXT;
ALTER TABLE source_registry ADD COLUMN retention_policy TEXT;
ALTER TABLE source_registry ADD COLUMN parser TEXT;
ALTER TABLE source_registry ADD COLUMN owner TEXT;
ALTER TABLE provider_access_registry ADD COLUMN owner TEXT;
