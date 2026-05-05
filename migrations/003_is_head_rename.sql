-- migrations/003_is_head_rename.sql
-- Accepted per ADR-013 and ADR-015.
-- Renames ambiguous is_current head-version flags to is_head.

BEGIN;

ALTER TABLE legal_documents
  RENAME COLUMN is_current TO is_head;

ALTER TABLE structure_nodes
  RENAME COLUMN is_current TO is_head;

ALTER TABLE annexes
  RENAME COLUMN is_current TO is_head;

ALTER TABLE forms
  RENAME COLUMN is_current TO is_head;

ALTER INDEX ux_legal_documents_current_act_title
  RENAME TO ux_legal_documents_head_act_title;

INSERT INTO schema_migrations (version, filename)
VALUES ('003', '003_is_head_rename.sql');

COMMIT;
