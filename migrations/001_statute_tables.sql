-- migrations/001_statute_tables.sql
-- Frozen per ADR-010 (Accepted 2026-04-29).
-- Cumulative state of ADRs 001-009 + ADR-010 image_filenames sub-decision.
-- All schema changes after this freeze ship as additive migrations.

------------------------------------------------------------
-- Table: legal_documents
-- Per ADR-002 (PK+UK), ADR-006 (doc_type CHECK), ADR-007 (doc_type_code),
-- ADR-008 (no JSONB), ADR-009 (parent_doc_id + asymmetric CHECK + indexes).
------------------------------------------------------------
CREATE TABLE legal_documents (
  doc_id                    BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  parent_doc_id             BIGINT NULL,
  law_id                    TEXT   NOT NULL,
  mst                       BIGINT NOT NULL,
  title                     TEXT   NOT NULL,
  title_abbrev              TEXT   NULL,
  law_number                TEXT   NOT NULL,
  doc_type                  TEXT   NOT NULL,
  doc_type_code             TEXT   NULL,
  amendment_type            TEXT   NOT NULL,
  enacted_date              DATE   NOT NULL,
  effective_date            DATE   NOT NULL,
  competent_authority       TEXT   NOT NULL,
  competent_authority_code  TEXT   NOT NULL,
  structure_code            TEXT   NULL,
  legislation_reason        TEXT   NULL,
  source_url                TEXT   NOT NULL,
  content_hash              TEXT   NOT NULL,
  effective_at              TIMESTAMPTZ NULL,
  superseded_at             TIMESTAMPTZ NULL,
  is_current                BOOLEAN NOT NULL DEFAULT TRUE,
  created_at                TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at                TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT uk_legal_documents_mst UNIQUE (mst),
  CONSTRAINT fk_legal_documents_parent FOREIGN KEY (parent_doc_id)
    REFERENCES legal_documents(doc_id) ON DELETE RESTRICT,
  CONSTRAINT chk_legal_documents_doc_type
    CHECK (doc_type IN ('법률', '대통령령', '총리령', '부령')),
  CONSTRAINT chk_legal_documents_act_no_parent
    CHECK (doc_type <> '법률' OR parent_doc_id IS NULL)
);

CREATE UNIQUE INDEX ux_legal_documents_current_act_title
  ON legal_documents (title)
  WHERE doc_type = '법률' AND is_current = TRUE;

CREATE INDEX ix_legal_documents_parent
  ON legal_documents (parent_doc_id)
  WHERE parent_doc_id IS NOT NULL;

------------------------------------------------------------
-- Table: structure_nodes
-- Per ADR-002 (PK+composite UK), ADR-006 (level CHECK).
------------------------------------------------------------
CREATE TABLE structure_nodes (
  node_id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  doc_id            BIGINT   NOT NULL,
  parent_id         BIGINT   NULL,
  level             SMALLINT NOT NULL,
  node_key          TEXT     NOT NULL,
  number            TEXT     NOT NULL,
  title             TEXT     NULL,
  content           TEXT     NOT NULL,
  sort_key          TEXT     NOT NULL,
  effective_date    DATE     NOT NULL,
  is_changed        BOOLEAN  NULL,
  source_url        TEXT     NULL,
  content_hash      TEXT     NOT NULL,
  effective_at      TIMESTAMPTZ NULL,
  superseded_at     TIMESTAMPTZ NULL,
  is_current        BOOLEAN  NOT NULL DEFAULT TRUE,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT fk_structure_nodes_doc FOREIGN KEY (doc_id)
    REFERENCES legal_documents(doc_id) ON DELETE RESTRICT,
  CONSTRAINT fk_structure_nodes_parent FOREIGN KEY (parent_id)
    REFERENCES structure_nodes(node_id) ON DELETE RESTRICT,
  CONSTRAINT uk_structure_nodes_doc_node_key UNIQUE (doc_id, node_key),
  CONSTRAINT chk_structure_nodes_level CHECK (level BETWEEN 1 AND 8)
);

------------------------------------------------------------
-- Table: supplementary_provisions
-- Per ADR-002 (PK+composite UK), ADR-004 (separate table),
-- ADR-005 (not a chunk source in Phase 1).
------------------------------------------------------------
CREATE TABLE supplementary_provisions (
  provision_id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  doc_id                BIGINT  NOT NULL,
  provision_key         TEXT    NOT NULL,
  promulgated_date      DATE    NOT NULL,
  promulgation_number   INTEGER NOT NULL,
  content               TEXT    NOT NULL,
  created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT fk_supplementary_provisions_doc FOREIGN KEY (doc_id)
    REFERENCES legal_documents(doc_id) ON DELETE RESTRICT,
  CONSTRAINT uk_supplementary_provisions_doc_key UNIQUE (doc_id, provision_key)
);

------------------------------------------------------------
-- Table: annexes
-- Per ADR-001 (separate from forms), ADR-002 (PK+composite UK),
-- ADR-008 (no JSONB), ADR-010 (image_filenames TEXT[]).
------------------------------------------------------------
CREATE TABLE annexes (
  annex_id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  doc_id            BIGINT NOT NULL,
  annex_key         TEXT   NOT NULL,
  number            TEXT   NOT NULL,
  branch_number     TEXT   NULL,
  title             TEXT   NOT NULL,
  content_text      TEXT   NOT NULL,
  content_format    TEXT   NULL,
  hwp_file_url      TEXT   NULL,
  hwp_filename      TEXT   NULL,
  pdf_file_url      TEXT   NULL,
  pdf_filename      TEXT   NULL,
  image_filenames   TEXT[] NULL,
  source_url        TEXT   NULL,
  content_hash      TEXT   NOT NULL,
  effective_at      TIMESTAMPTZ NULL,
  superseded_at     TIMESTAMPTZ NULL,
  is_current        BOOLEAN NOT NULL DEFAULT TRUE,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT fk_annexes_doc FOREIGN KEY (doc_id)
    REFERENCES legal_documents(doc_id) ON DELETE RESTRICT,
  CONSTRAINT uk_annexes_doc_key UNIQUE (doc_id, annex_key)
);

------------------------------------------------------------
-- Table: forms
-- Per ADR-001 (separate from annexes), ADR-002 (PK+composite UK),
-- ADR-008 (no JSONB), ADR-010 (image_filenames TEXT[]).
-- Note: no content_hash because no content_text (forms are
-- metadata-only per ADR-001).
------------------------------------------------------------
CREATE TABLE forms (
  form_id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  doc_id            BIGINT NOT NULL,
  form_key          TEXT   NOT NULL,
  number            TEXT   NOT NULL,
  branch_number     TEXT   NULL,
  title             TEXT   NOT NULL,
  hwp_file_url      TEXT   NULL,
  hwp_filename      TEXT   NULL,
  pdf_file_url      TEXT   NULL,
  pdf_filename      TEXT   NULL,
  image_filenames   TEXT[] NULL,
  source_url        TEXT   NULL,
  effective_at      TIMESTAMPTZ NULL,
  superseded_at     TIMESTAMPTZ NULL,
  is_current        BOOLEAN NOT NULL DEFAULT TRUE,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT fk_forms_doc FOREIGN KEY (doc_id)
    REFERENCES legal_documents(doc_id) ON DELETE RESTRICT,
  CONSTRAINT uk_forms_doc_key UNIQUE (doc_id, form_key)
);
