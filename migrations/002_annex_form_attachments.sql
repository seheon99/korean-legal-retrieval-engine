-- migrations/002_annex_form_attachments.sql
-- Accepted per ADR-014 and ADR-015.
-- Adds owner-specific attachment provenance tables for annexes and forms.

BEGIN;

CREATE TABLE IF NOT EXISTS schema_migrations (
  version     TEXT PRIMARY KEY,
  filename    TEXT NOT NULL,
  applied_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO schema_migrations (version, filename)
VALUES ('001', '001_statute_tables.sql')
ON CONFLICT (version) DO NOTHING;

CREATE TABLE annex_attachments (
  attachment_id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  annex_id               BIGINT NOT NULL,
  attachment_type        TEXT   NOT NULL,
  source_attachment_url  TEXT   NULL,
  source_filename        TEXT   NULL,
  stored_file_path       TEXT   NULL,
  checksum_sha256        TEXT   NULL,
  fetched_at             TIMESTAMPTZ NULL,
  CONSTRAINT fk_annex_attachments_annex FOREIGN KEY (annex_id)
    REFERENCES annexes(annex_id) ON DELETE RESTRICT,
  CONSTRAINT chk_annex_attachments_type
    CHECK (attachment_type IN ('hwp', 'pdf', 'image'))
);

CREATE INDEX ix_annex_attachments_annex
  ON annex_attachments (annex_id);

CREATE INDEX ix_annex_attachments_type
  ON annex_attachments (attachment_type);

CREATE TABLE form_attachments (
  attachment_id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  form_id                BIGINT NOT NULL,
  attachment_type        TEXT   NOT NULL,
  source_attachment_url  TEXT   NULL,
  source_filename        TEXT   NULL,
  stored_file_path       TEXT   NULL,
  checksum_sha256        TEXT   NULL,
  fetched_at             TIMESTAMPTZ NULL,
  CONSTRAINT fk_form_attachments_form FOREIGN KEY (form_id)
    REFERENCES forms(form_id) ON DELETE RESTRICT,
  CONSTRAINT chk_form_attachments_type
    CHECK (attachment_type IN ('hwp', 'pdf', 'image'))
);

CREATE INDEX ix_form_attachments_form
  ON form_attachments (form_id);

CREATE INDEX ix_form_attachments_type
  ON form_attachments (attachment_type);

INSERT INTO schema_migrations (version, filename)
VALUES ('002', '002_annex_form_attachments.sql');

COMMIT;
