# ADR-010 — Phase-1 statute-DDL freeze

- **Status**: Accepted
- **Date**: 2026-04-29
- **Context layer**: Statute (성문규범) ERD
- **Resolves**:
  1. Meta-decision to commit Phase-1 DDL as
     `migrations/001_statute_tables.sql` ahead of TODO-2, TODO-5,
     and TODO-7 resolution.
  2. ADR-008's deferred sub-decision on `image_filenames`
     representation (resolved: `TEXT[]` on both `annexes` and
     `forms`).
- **Depends on / aligned with**: ADR-001 through ADR-009 (cumulative
  freeze content). Specifically:
  - ADR-001 — `annexes` and `forms` split into separate tables
  - ADR-002 — BIGINT IDENTITY PK + natural-key UNIQUE pattern
    across all 5 tables
  - ADR-003 — chunks FK shape (out-of-scope for _this_ migration;
    chunks ships separately when retrieval-pipeline design lands)
  - ADR-004 — `supplementary_provisions` stays a separate table
  - ADR-005 — `supplementary_provisions` is not a chunk source in
    Phase 1 (so no `provision_id` FK on the future chunks table)
  - ADR-006 — `doc_type` TEXT+CHECK; `level` SMALLINT+CHECK
  - ADR-007 — `doc_type_code TEXT NULL` sibling column on
    `legal_documents`
  - ADR-008 — no JSONB `metadata` column on statute tables;
    promote-or-omit-or-retain-raw-XML policy
  - ADR-009 — `parent_doc_id` self-FK with asymmetric CHECK and
    two committed indexes
- **Out of scope (not decided here)**:
  1. The `chunks` table DDL — separate migration; ships with
     retrieval-pipeline design.
  2. Migration-tooling choice (Alembic vs raw SQL vs Sqitch vs
     other). The freeze names the file path
     `migrations/001_statute_tables.sql` but does not commit to a
     specific tool.
  3. Test fixtures, seed data, ingestion-pipeline specifics.
  4. Performance tuning beyond ADR-009's two committed indexes and
     the implicit indexes auto-created by UNIQUE constraints
     (TODO-7).
  5. `updated_at` automation mechanism (BEFORE-UPDATE trigger vs
     application-level handling). The column is in the freeze;
     the update mechanism is implementation-side.
  6. Schema namespacing (`CREATE SCHEMA …`). Phase 1 lands in the
     default `public` schema.
  7. ADR-008's raw-API-XML retention dependency — separate
     ingestion-pipeline decision; ADR-010 freezes the schema under
     the assumption that retention will be committed elsewhere.

## Context

The Phase-1 statute ERD has converged across nine ADRs:

| ID      | Decision                                               | Frozen artefact                                             |
| ------- | ------------------------------------------------------ | ----------------------------------------------------------- |
| ADR-001 | Split `annexes` and `forms`                            | Two separate tables                                         |
| ADR-002 | BIGINT IDENTITY + natural-key UNIQUE                   | All 5 tables                                                |
| ADR-003 | Split FK columns on chunks                             | (out of this migration)                                     |
| ADR-004 | `supplementary_provisions` separate                    | Table present                                               |
| ADR-005 | `supplementary_provisions` not a chunk source          | (no `provision_id` FK on future chunks)                     |
| ADR-006 | `doc_type` / `level` CHECK constraints                 | `chk_legal_documents_doc_type`, `chk_structure_nodes_level` |
| ADR-007 | `doc_type_code` sibling column                         | Column on `legal_documents`                                 |
| ADR-008 | No JSONB `metadata` on statute tables                  | (no metadata columns)                                       |
| ADR-009 | `parent_doc_id` self-FK + asymmetric CHECK + 2 indexes | Column, FK, CHECK, two indexes                              |

Three open TODOs remain. Audited for whether each blocks the freeze:

| TODO                                                  | State                                                         | Verdict for the freeze                                                                                                                                                                                                                                                               |
| ----------------------------------------------------- | ------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| TODO-2 — Cross-statute citations (Criminal Code etc.) | Blocked on T15 (commentary inventory); Phase-2-ish            | **Additive.** Adds either a new column on `structure_nodes` (e.g., `cross_refs JSONB`) or a new `document_relations` edge-list table. Neither requires a destructive change to the frozen tables.                                                                                    |
| TODO-5 — `node_id` retention across amendments        | Phase-2 temporality concern                                   | **Additive.** The frozen schema already includes `effective_at`, `superseded_at`, `is_current` columns to support either retention policy (immutable-rows on amendment, or update-in-place). TODO-5 picks the _operational rule_; the schema accommodates both shapes without ALTER. |
| TODO-7 — Index strategy ratification                  | Deferred-by-design ("measure first" per design principle #13) | **Additive.** New indexes can land in later migrations without affecting existing tables. ADR-009's two committed indexes are already in the freeze.                                                                                                                                 |

The decision matters because: continuing to defer DDL postpones every
downstream task — ingestion pipeline, query layer, retrieval
pipeline, evaluation harness. None can begin without a schema. The
walking-skeleton principle (Phase 1 = single statute end-to-end)
treats schema commitment as a precondition for end-to-end. The open
TODOs are not schema convergence problems; they are future features
that the current schema accommodates additively.

## Decision

Freeze the Phase-1 statute schema as `migrations/001_statute_tables.sql`
with the canonical content below. Future schema changes ship as
additive migrations (`002_*.sql`, `003_*.sql`, …).

**Sub-decision (resolves ADR-008 "Out of scope" #2)**:
`image_filenames` is `TEXT[]` (PostgreSQL native array) on both
`annexes` and `forms`. Justification: small, ordered list of file
names; no key-value semantics; consistent with ADR-008's no-JSONB
stance on statute tables. PostgreSQL arrays support `ANY()` queries
and GIN indexing if ever needed.

### Canonical schema

```sql
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
```

### Notes on the freeze

- **Implicit indexes from PK and UNIQUE.** PostgreSQL auto-creates
  B-tree indexes on every PK and on every UNIQUE constraint. The
  composite UNIQUE constraints on the four child tables
  (`(doc_id, node_key)`, `(doc_id, provision_key)`,
  `(doc_id, annex_key)`, `(doc_id, form_key)`) cover doc_id-leftmost-
  prefix queries — no separate FK-only index is needed for Phase 1.
  Adding FK-only indexes on `parent_id` (structure_nodes self-ref)
  or anywhere else is a TODO-7 concern and ships in a later
  migration if measurement justifies it.
- **`ON DELETE RESTRICT` on every FK.** Consistent with ADR-009's
  reasoning: the lifecycle is soft-delete via `is_current`, not
  hard-delete. Hard-deletes should fail loudly.
- **Temporality columns** (`effective_at`, `superseded_at`,
  `is_current`) are present on every table with a temporal lifecycle.
  Phase-1 ingestion populates `is_current = TRUE`; Phase-2 work
  (TODO-5) chooses the rule for flipping them. The schema does not
  pre-decide between immutable-rows and update-in-place — both fit.
- **No `updated_at` trigger committed.** The column is in the
  schema but the auto-update mechanism (BEFORE UPDATE trigger vs
  application-level handling) is implementation-side. Either approach
  satisfies the column's semantic.
- **Schema namespacing** is left at the default `public`. Phase 2
  may introduce dedicated schemas (e.g., `statute`, `judicial`,
  `chunks`) when other category ERDs land; that is a separate
  decision.

## Options considered

| Option                                                              | Verdict                |
| ------------------------------------------------------------------- | ---------------------- |
| **A. Freeze now per the cumulative ADR state**                      | **accepted**           |
| B. Defer freeze until TODO-2, TODO-5, TODO-7 are all resolved       | rejected — see "vs. B" |
| C. Incremental freeze (ship one table at a time)                    | rejected — see "vs. C" |
| D. Skip migrations; let an ORM (SQLAlchemy / SQLModel) generate DDL | rejected — see "vs. D" |

### Why A over B — defer until full TODO resolution

B's appeal is intuitive: don't freeze a schema you know is incomplete.
The arguments **for** B:

1. TODO-2 might surface a `structure_nodes` column or a
   relationship that would have been cleaner to include from day
   one.
2. TODO-5's amendment-retention policy interacts with how
   `structure_nodes` is used at scale.
3. TODO-7's measured indexes might want to land alongside the
   table definitions for cleanliness.

Why B loses:

1. **The open TODOs are additive.** Each was audited above:
   TODO-2 (new column or new table), TODO-5 (operational rule, not
   schema), TODO-7 (additive indexes). None requires a destructive
   change. PostgreSQL's `ALTER TABLE ADD COLUMN`, `CREATE INDEX`,
   and `CREATE TABLE` are exactly the additive migrations that
   migration tooling exists to make routine.
2. **TODO-2 is blocked on external work** (T15 commentary
   inventory). Making the freeze contingent on TODO-2 means
   waiting indefinitely for non-schema-side work.
3. **Walking-skeleton** is the explicit Phase-1 framing. Phase 1 =
   single statute end-to-end. End-to-end requires schema
   commitment as a precondition. Deferring DDL ratifies nothing
   downstream.
4. **Schema discipline survives migrations.** "Don't freeze until
   you're sure" treats migrations as a failure mode. They aren't;
   they're how production schemas evolve. Future ADR commitments
   land via ALTER, not via re-freezing.

### Why A over C — incremental freeze

C ("freeze `legal_documents` now, defer the others until each is
fully resolved") has surface appeal: ship the most converged table
first.

Why C loses:

1. **The five tables are FK-coupled.** `structure_nodes`,
   `supplementary_provisions`, `annexes`, `forms` all reference
   `legal_documents`. They cannot be added separately without
   placeholder constraints, and the natural-key UNIQUE indexes on
   the child tables depend on the parent FK target existing.
   Splitting introduces ordering dependencies for no benefit.
2. **The other four tables are no less converged than
   `legal_documents`.** ADR-002 closed all five simultaneously.
   ADR-004 and ADR-005 finalized `supplementary_provisions`
   semantics. ADR-001 finalized the annexes/forms split. There is
   no "more uncertain" table to defer.

### Why A over D — ORM-generated DDL

D would skip the migration file entirely and let a Python ORM emit
DDL on startup or via a `Base.metadata.create_all()` call.

Why D loses:

1. **CLAUDE.md commits to migrations from day 1**: "DDL versioned
   from day 1" (Documentation Layout, §7).
2. **ORM-generated DDL hides schema decisions** behind ORM
   metaprogramming. The portfolio asset is the schema and its
   reasoning; emitting it through ORM machinery makes the schema
   harder to read and harder to defend.
3. **CHECK constraints, partial indexes, and named constraints**
   are awkward to express portably across ORM layers. SQLAlchemy
   supports them but at the cost of leaking `text(...)` clauses
   into model definitions.
4. **Reproducibility.** A frozen SQL file is byte-identical across
   environments. ORM-generated DDL depends on ORM version, Python
   version, and metadata-emission code paths.

## Trade-offs accepted

- **Future schema changes ship as migrations, not edits.**
  Standard production practice; not a real cost.
- **If a missed Phase-1 decision surfaces, it may force a
  non-additive migration.** Mitigated by the 9-ADR audit: every
  table-shape decision has been examined explicitly. The most
  likely missed-decision risks (column-type narrowing, constraint
  tightening) are inherently additive in PostgreSQL via `ALTER
COLUMN`.
- **The freeze locks in `image_filenames TEXT[]`.** If per-image
  metadata grows (e.g., display order, dimensions, alt text), a
  Phase-2 migration shifts to a child table or JSONB. Probability
  is low; PostgreSQL `TEXT[]` handles arrays of plain strings
  cleanly.
- **Soft commitment from ADR-008** (raw API XML retention) is not
  ratified by this ADR. ADR-010 freezes the schema; ADR-008's
  retention dependency requires a separate ingestion-pipeline
  decision. The freeze is correct under that dependency; if the
  dependency is later ruled out, ADR-008's fallback (Option D
  named-field allowlist JSONB on `legal_documents`) requires its
  own migration.
- **Default schema (`public`).** If Phase 2 adopts namespaced
  schemas, all five tables move via `ALTER TABLE … SET SCHEMA …`,
  which is non-destructive but visible.

## Consequences

- **Green-light to write `migrations/001_statute_tables.sql`** with
  the canonical content above. The file lands as a separate
  artefact after this ADR is Accepted.
- **ERD draft `Status`** flips from "Draft for human review" to
  "Frozen — see `migrations/001_statute_tables.sql` per ADR-010".
- **CLAUDE.md §4** updates to reflect ADR-010 acceptance and the
  shift from ERD-design phase to ingestion-pipeline / query-layer
  design phase.
- **Future ADRs** operate on the frozen baseline. TODO-2, TODO-5,
  TODO-7 resolution shapes will be `migrations/00X_*.sql` files,
  each accompanied by an ADR (or noted as additive ratification if
  the change is small).
- **Open ERD TODOs (TODO-2, TODO-5, TODO-7)** remain open in the
  ERD draft, now reframed as Phase-2 (or Phase-2-ish) work that
  ships as additive migrations rather than as Phase-1 blockers.
- **The next decision-shape shift**: from schema design to
  ingestion-pipeline design. The pipeline must implement ADR-009's
  Phase-1 population rule, ADR-008's raw-XML retention dependency
  (or surface that retention is not committed), and ADR-006's
  verification trigger for ministry-prefixed `doc_type` variants.

## Verification once accepted

1. **`migrations/001_statute_tables.sql`** is created and matches
   the canonical schema above.
2. **`migrations/`** directory exists at the repo root (verified
   already; currently empty).
3. **ERD draft `Status` line** updated.
4. **CLAUDE.md §4** updated.
5. **No changes to ADR-001 through ADR-009 invariants.** This is
   the ratification ADR; it does not modify prior decisions.
6. **`docs/sessions/`** captures the freeze as an artefact of the
   session (per §8 Session Protocol).

## Revisit triggers

ADR-010 is revisited if any of the following hold:

- **Phase-2 work surfaces a non-additive schema change
  requirement.** E.g., TODO-5 lands on Option B (update-in-place)
  and discovers that the `effective_at` / `superseded_at` columns
  must be redefined as something other than nullable
  `TIMESTAMPTZ`. Action: the new ADR documents the destructive
  change and the migration shape.
- **A foundational error is discovered post-freeze.** E.g., a
  CHECK constraint rejects a valid value class observed in
  ingestion. Action: hot-fix migration; ADR-010 is amended with a
  "freeze breach" note rather than re-issued.
- **Migration tooling choice forces a re-shape.** E.g., chosen
  tool doesn't support partial UNIQUE indexes inline. Action:
  tooling choice is its own decision; the schema spec stays
  canonical.
- **ADR-008's retention dependency is ruled out** (ingestion
  pipeline decides not to retain raw XML). Action: ADR-008
  fallback (Option D) requires a migration; ADR-010's freeze
  authority covers that follow-up migration.
- **Schema namespacing is adopted Phase-2.** Action: non-
  destructive `ALTER TABLE … SET SCHEMA …` migration; not a
  freeze breach.

## What is checked vs. what is still open

**Checked (this ADR):**

- 9-ADR audit confirms internal coherence of the freeze content.
- Each open TODO (TODO-2, TODO-5, TODO-7) is additive — does not
  require a destructive change to the frozen tables.
- `image_filenames` shape resolved: `TEXT[]` on `annexes` and
  `forms` (closes ADR-008 "Out of scope" #2).
- `migrations/` directory exists and is empty (canonical file
  location confirmed).

**Still open (deferred):**

- Migration tooling choice.
- Test fixtures and seed data.
- `updated_at` automation mechanism.
- Indexes beyond ADR-009's two committed indexes (TODO-7).
- ADR-008's retention dependency (separate ingestion-pipeline
  decision).
- Schema namespacing.

## References

- `docs/legal-erd-draft.md` — frozen ERD source
- `docs/decisions/ADR-001` through `ADR-009` — cumulative freeze
  content
- `docs/api-samples/` — empirical evidence anchoring the schema
- `CLAUDE.md` §7 — `migrations/` directory commitment ("DDL
  versioned from day 1")
