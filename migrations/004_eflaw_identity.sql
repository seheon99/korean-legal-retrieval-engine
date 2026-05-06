-- migrations/004_eflaw_identity.sql
-- Accepted per ADR-020.
-- `mst` alone is not a canonical source-row identity when staged
-- effective-date slices exist under target=eflaw.

BEGIN;

ALTER TABLE legal_documents
  DROP CONSTRAINT uk_legal_documents_mst;

ALTER TABLE legal_documents
  ADD CONSTRAINT uk_legal_documents_law_mst_effective_date
  UNIQUE (law_id, mst, effective_date);

INSERT INTO schema_migrations (version, filename)
VALUES ('004', '004_eflaw_identity.sql');

COMMIT;
