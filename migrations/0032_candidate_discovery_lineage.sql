PRAGMA foreign_keys=ON;
ALTER TABLE candidate_plan_intakes ADD COLUMN discovery_evidence_json TEXT NOT NULL DEFAULT '[]';
