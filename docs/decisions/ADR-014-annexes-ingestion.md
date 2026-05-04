# ADR-014 — `annexes` ingestion and parallel attachment tables

- **Status**: Accepted
- **Date**: 2026-05-04
- **Context layer**: Statute (성문규범) ingestion pipeline —
  `annexes`, `annex_attachments`, `form_attachments`
- **Resolves**:
  - The remaining Phase-1 statute child-table path that is also a chunk
    source: Decree annexes (`별표`).
  - Concrete field mapping for `annexes`, `annex_attachments`, and the
    future `form_attachments` table.
  - Verification boundary for the API's `<별표단위>` discriminator and
    key suffix contract.
  - Separation of upstream attachment provenance from application-owned
    binary storage.
  - Retrieval semantics: annexes are legal meaning units and chunk
    sources; forms are metadata-only; attachments are not search units.
- **Amends**:
  - **ADR-010 (Accepted)** — `annexes` and `forms` should no longer
    carry HWP/PDF/image attachment columns directly. Binary references
    move to parallel attachment tables via an additive migration.
- **Depends on / aligned with**:
  - **ADR-001 (Accepted)** — annexes and forms are split; annexes are a
    chunk source, forms are not.
  - **ADR-002 (Accepted)** — `annex_id BIGINT IDENTITY` primary key plus
    `(doc_id, annex_key)` natural-key UNIQUE.
  - **ADR-003 (Accepted)** — future `chunks` may point to
    `annexes.annex_id`; forms are excluded.
  - **ADR-008 (Accepted)** — no JSONB fallback on statute source tables.
  - **ADR-010 (Accepted)** — Phase-1 DDL was frozen before attachment
    provenance/storage was separated. This ADR requires an additive
    migration for `annex_attachments` and `form_attachments`.
  - **ADR-011 (Accepted)** — raw XML is retained under `data/raw/` as the
    fallback for unpromoted fields and future reparsing.
- **Out of scope (not decided here)**:
  1. `forms` ingestion beyond preserving the existing ADR-001 split,
     discriminator boundary, and `form_attachments` table shape.
  2. HWP/PDF/image binary download execution and retention operations.
     This ADR defines attachment-reference rows and storage fields; it
     does not require downloading binaries in Phase 1.
  3. Table-aware parsing of `<별표내용>` into structured rows/cells.
     Phase 1 stores the inline text as the search target.
  4. `chunks` table DDL and chunking strategy for annex bodies.
  5. Amendment temporality for annexes (`effective_at`,
     `superseded_at`, `is_head`). ADR-013 defines the source-row
     lifecycle; this ADR only maps `<별표단위>` fields into an annex row.

## Context

After ADR-012, the ingestion pipeline can populate `legal_documents` and
`structure_nodes` end-to-end for the Phase-1 Act and Decree. The next
remaining statute child table that matters for retrieval is `annexes`.

ADR-001 already settled the model-level split:

- `annexes` (`별표`) contain substantive delegated provisions and are a
  first-class chunk source.
- `forms` (`서식`) are metadata-only for retrieval purposes and must not
  feed body text into chunks.

What remains undecided is the ingestion contract: exactly which XML rows
enter `annexes`, which attachment-reference rows are produced, how values
are normalized, and what should halt ingestion when the API shape violates
the assumptions behind ADR-001 and ADR-010.

Retrieval units must be legal meaning units, not files:

```text
annexes
  -> chunks
  -> BM25 index
  -> vector embeddings

forms
  -> metadata only
  -> not indexed in Phase 1

attachments
  -> source/provenance + optional storage metadata
  -> not indexed directly
```

Attachments may later be used to extract text or display/download a
source artifact, but they are not first-class retrieval documents.

The Phase-1 Decree sample `data/raw/014159/277417.xml` contains five
`<별표단위>` rows under `<별표>`. All five have:

- `<별표구분>별표</별표구분>`
- `별표키` ending in `E`
- inline `<별표내용>` text
- HWP/PDF links and filenames
- one or more `<별표이미지파일명>` elements

The Act sample `data/raw/013993/228817.xml` has no annex rows.

## Decision

Implement `parse_annexes(doc: Document) -> list[Annex]` and
`parse_annex_attachments(doc: Document) -> list[AnnexAttachment]`.
Insert annex rows from `_insert_children()` after `structure_nodes`, then
insert each annex's attachment-reference rows after the owning `annex_id`
is known.

The parser walks every `<별표>/<별표단위>` row, validates the
discriminator/key/body-field contract for both `별표` and `서식`, and
inserts only rows where `<별표구분>별표</별표구분>` into `annexes`. Rows
with `<별표구분>서식</별표구분>` are validated but not inserted into
`annexes`; they remain reserved for a later `forms` parser.

### Field mapping

| Column | XML source / rule |
|--------|-------------------|
| `doc_id` | Current parent `legal_documents.doc_id` at insert time |
| `annex_key` | `<별표단위 별표키>` verbatim |
| `number` | Normalized display number from `<별표번호>` |
| `branch_number` | `<별표가지번호>` normalized; `NULL` when absent or `00` |
| `title` | `<별표제목>` stripped of surrounding whitespace |
| `content_text` | Normalized `<별표내용>` text per "Content text normalization" below |
| `content_format` | `NULL` in Phase 1 |
| `source_url` | `NULL` in Phase 1; no stable node-level URL is available yet |
| `content_hash` | SHA-256 of `content_text` UTF-8 bytes |
| `effective_at` / `superseded_at` / `is_head` | Use the parent document ingestion lifecycle from ADR-013 |

### Parallel attachment tables

Attachment links emitted by the source API are stored as source
provenance and replay metadata only. They are not stable, user-facing
URLs and must not be overwritten with application-controlled storage
locations.

Use parallel owner-specific attachment tables:

```sql
CREATE TABLE annex_attachments (
  attachment_id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  annex_id               BIGINT NOT NULL REFERENCES annexes(annex_id),
  attachment_type        TEXT   NOT NULL,
  source_attachment_url  TEXT   NULL,
  source_filename        TEXT   NULL,
  stored_file_path       TEXT   NULL,
  checksum_sha256        TEXT   NULL,
  fetched_at             TIMESTAMPTZ NULL
);

CREATE TABLE form_attachments (
  attachment_id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  form_id                BIGINT NOT NULL REFERENCES forms(form_id),
  attachment_type        TEXT   NOT NULL,
  source_attachment_url  TEXT   NULL,
  source_filename        TEXT   NULL,
  stored_file_path       TEXT   NULL,
  checksum_sha256        TEXT   NULL,
  fetched_at             TIMESTAMPTZ NULL
);
```

Field semantics:

| Column | Rule |
|--------|------|
| `annex_id` / `form_id` | Owning source row. This is the only structural difference between the two tables |
| `attachment_type` | `hwp`, `pdf`, or `image` |
| `source_attachment_url` | Exact upstream API value; may be relative; not stable or user-facing |
| `source_filename` | Original filename emitted by the API |
| `stored_file_path` | Application-controlled durable storage path; `NULL` until downloaded |
| `checksum_sha256` | SHA-256 of downloaded binary bytes; `NULL` until downloaded |
| `fetched_at` | Download timestamp; `NULL` until downloaded |

Semantic difference:

| Table | Owner | Role |
|-------|-------|------|
| `annex_attachments` | `annexes` | Supporting artifacts for annex legal content. The annex row, not the attachment, is the retrieval source |
| `form_attachments` | `forms` | Primary usable artifacts for metadata-only form records. Still not indexed in Phase 1 |

XML mapping:

| Attachment row | XML source |
|----------------|------------|
| `hwp` | `<별표서식파일링크>` -> `source_attachment_url`; `<별표HWP파일명>` -> `source_filename` |
| `pdf` | `<별표서식PDF파일링크>` -> `source_attachment_url`; `<별표PDF파일명>` -> `source_filename` |
| `image` | one row per `<별표이미지파일명>`; `source_filename` set to the image filename; `source_attachment_url = NULL` unless a future API field exposes one |

Phase 1 does not download binaries. Therefore `stored_file_path`,
`checksum_sha256`, and `fetched_at` are `NULL` for every inserted
attachment row.

### Why parallel tables

Use parallel tables (`annex_attachments`, `form_attachments`) rather than a
single shared `attachments` table.

Rejected option: polymorphic association.

```sql
attachments (
  attachment_id BIGINT,
  owner_type TEXT,
  owner_id BIGINT
)
```

This cannot enforce referential integrity cleanly and conflicts with the
ADR-003 direction: prefer explicit FKs over polymorphic source references.

Rejected option: one shared table with multiple nullable owner FKs.

```sql
attachments (
  attachment_id BIGINT,
  annex_id BIGINT NULL,
  form_id BIGINT NULL
)
```

This requires exactly-one-owner CHECK constraints and gets noisier as
owner types grow.

Parallel tables are intentional duplication, not a DRY violation. DRY is
about eliminating duplicated knowledge, not necessarily duplicated table
shape. Here, the storage/provenance fields have the same meaning, but the
ownership semantics differ and should stay explicit.

### No `attachment_blobs` in Phase 1

Do not introduce an `attachment_blobs` table in Phase 1.

Blob abstraction is premature because current requirements do not include:

- checksum-based deduplication
- shared file reuse across attachments
- reprocessing/refetch lifecycle management
- storage garbage collection
- storage-backend abstraction such as S3 object keys

Blob abstraction does not improve retrieval quality. Search targets are
chunks derived from `annexes`, not attachments, blobs, or raw files.

Revisit a blob layer only when deduplication, shared reuse, refetch
lifecycle, garbage collection, or storage-backend abstraction becomes
load-bearing. A future blob table can be added without changing the
owner-specific attachment semantics chosen here.

### Number normalization

`number` is a display number, not a key.

Normalize `<별표번호>` from the API's fixed-width form to a citation-facing
form:

| XML value | Stored `number` |
|-----------|------------------|
| `0001` | `1` |
| `0012` | `12` |

`branch_number` is stored only when the appendix is actually branched:

| XML value | Stored `branch_number` |
|-----------|------------------------|
| absent | `NULL` |
| `00` | `NULL` |
| `02` | `2` |

The rendered label can be reconstructed as `별표 {number}` when
`branch_number IS NULL`, and `별표 {number}의{branch_number}` otherwise.
The natural key remains `annex_key`; normalized display fields do not
participate in identity.

### Content text normalization

`content_text` is the exact string used for `content_hash`, so parser
normalization is part of the data contract.

For `<별표내용>`:

1. Concatenate the element's text and descendants in XML order.
2. Normalize line endings to LF (`\n`): CRLF and bare CR become LF.
3. Strip only outer whitespace from the full concatenated string.
4. Preserve internal spaces, indentation, blank lines, and table-like
   layout text after the outer strip.

`content_hash` is SHA-256 of this stored `content_text` encoded as UTF-8.
The parser must not hash the raw XML fragment, an unstripped value, or a
separately normalized variant.

### Key and discriminator verification

Halt ingestion on any violation:

1. `별표키` must match `^[0-9]{6}[EF]$`.
2. `별표구분=별표` rows must have `별표키` ending in `E`.
3. `별표구분=서식` rows must have `별표키` ending in `F`.
4. Unknown or empty `별표구분` is an ingest error, not an omitted row.
5. The decoded key number must match `<별표번호>`:
   - `별표키[0:4]` is the canonical 4-digit number segment.
   - `<별표번호>` must be numeric and canonicalize to that same 4-digit
     segment.
   - stored `number` is the citation-facing integer string from the same
     value (`0002` → `2`).
6. The decoded key branch must match `<별표가지번호>`:
   - `별표키[4:6]` is the canonical 2-digit branch segment.
   - missing `<별표가지번호>` canonicalizes to `00`.
   - present `<별표가지번호>` must be numeric and canonicalize to the same
     2-digit segment.
   - stored `branch_number` is `NULL` for `00`, otherwise the
     citation-facing integer string (`02` → `2`).
7. Annex rows must have non-empty `별표제목` and normalized
   `별표내용`.
8. Duplicate `annex_key` values within one document are an ingest error
   before reaching the database UNIQUE constraint.

This makes ADR-001's split executable: the discriminator is authoritative,
the key suffix is a cross-check, and mismatch means the parser assumption
needs review.

### Attachment source/storage separation

Do not overwrite source data. The ingestion contract does not replace or
normalize source links into application-controlled storage locations.

`source_attachment_url` stores the exact value emitted by the upstream API.
It may be a relative path, may become invalid over time, and is retained
only for provenance, replay/refetch, debugging, and audit.

`stored_file_path` is the application-controlled location where the binary
is actually stored after a download step. It is the only reliable retrieval
path, but it may be `NULL` when binaries have not been downloaded.

### Insert behavior

`_insert_children()` inserts annexes in XML parse order after
`structure_nodes`. It must use `RETURNING annex_id` and maintain an
in-memory `annex_key -> annex_id` map so `annex_attachments` rows can
reference the owning annex. `form_attachments` are not inserted in the
Phase-1 corpus because the Phase-1 Act/Decree samples contain zero forms.

The current idempotency policy remains document-level:

- same `mst` + same `legal_documents.content_hash` → skip the whole
  document, including child inserts
- same `mst` + different hash → current `ContentMismatchError` path

Because `_skip_if_present()` skips unchanged documents, adding annex
ingestion after documents already exist requires either a deliberate
backfill for existing rows or a clean dev DB reload. That is an
implementation operation, not a schema decision.

## Options considered

| Option | Verdict |
|--------|---------|
| A. Insert only `별표구분=별표` into `annexes`, verify `E/F` suffixes, write annex attachment references to `annex_attachments`, define parallel `form_attachments`, leave forms parser for later | **accepted** — matches ADR-001 and keeps Phase-1 scope on the remaining chunk source |
| B. Parse annexes and forms together now | rejected — forms are absent in the Phase-1 corpus and are not a chunk source; this expands surface without improving the walking skeleton |
| C. Store `별표번호` exactly as `0001` | rejected — fixed-width API encoding is key-like, while `number` is a display column; normalized `1` matches citation behavior and mirrors the `structure_nodes.number` cleanup |
| D. Keep HWP/PDF/image columns on `annexes` | rejected — mixes source provenance with binary storage concerns and forces repeated attachment groups onto the annex body row |
| E. Keep HWP/PDF/image columns on `forms` | rejected — the same source/storage separation applies to form files; use `form_attachments` |
| F. Use one polymorphic `attachments(owner_type, owner_id)` table | rejected — no clean DB-level FK; conflicts with ADR-003 |
| G. Use one table with nullable `annex_id` / `form_id` owner FKs | rejected — requires CHECK constraints and scales poorly as owner types grow |
| H. Add `attachment_blobs` now | rejected for Phase 1 — no dedupe, shared reuse, lifecycle, GC, or storage-backend abstraction requirement |
| I. Convert attachment URLs to absolute `https://www.law.go.kr/...` URLs during ingest | rejected for Phase 1 — binary download semantics and OC-key behavior are not decided; store API output verbatim |
| J. Infer `content_format` (`prose` / `table` / `mixed`) from ASCII layout heuristics now | rejected — useful later for chunking, but heuristic classification is not needed for source ingestion |

## Consequences

- The Decree's five appendices become queryable source rows and can later
  feed `chunks` through `annexes.annex_id`.
- Phase-1 still avoids parsing HWP/PDF/image binaries. Inline
  `<별표내용>` is the search target.
- Upstream attachment references are preserved in `annex_attachments`
  without treating them as stable fetch or user-facing URLs.
- Future form file references use `form_attachments` with the same
  provenance/storage semantics.
- Durable binary storage, when implemented, writes to `stored_file_path`
  without overwriting source provenance.
- No `attachment_blobs` table ships in Phase 1.
- `forms` remain intentionally unimplemented until a corpus with forms
  enters scope or metadata search requires them.
- The parser now has three child-table paths:
  `structure_nodes`, `annexes`, and `annex_attachments`.
  `supplementary_provisions` remains the next persistence-only child table
  after annexes.
- Existing dev data must be backfilled or reloaded to populate annexes
  because idempotent re-ingest skips unchanged documents.

## Test plan

Focused parser tests:

- Act `data/raw/013993/228817.xml` yields `0` annexes.
- Decree `data/raw/014159/277417.xml` yields `5` annexes.
- Decree annex keys are exactly:
  `000100E`, `000200E`, `000300E`, `000400E`, `000500E`.
- Numbers normalize to `1` through `5`.
- `branch_number` is `None` for all five Phase-1 Decree annexes.
- `annex_attachments` contains 21 rows for the Phase-1 Decree sample:
  10 HWP/PDF rows plus 11 image rows.
- `source_attachment_url` preserves exact API values for HWP/PDF rows.
- image attachment rows preserve filename order and have
  `source_attachment_url = NULL`.
- `stored_file_path`, `checksum_sha256`, and `fetched_at` are `NULL` in
  Phase 1.
- ADR text states attachments are not retrieval documents and are not
  indexed directly.
- ADR text states no `attachment_blobs` table in Phase 1.
- `content_hash` equals SHA-256 of `content_text`.
- No duplicate `annex_key` values per document.

Negative parser tests:

- invalid `별표키` shape
- `별표구분=별표` with `F` suffix
- `별표구분=서식` with `E` suffix
- unknown or empty `별표구분`
- key number mismatch (`별표키[0:4]` disagrees with `<별표번호>`)
- key branch mismatch (`별표키[4:6]` disagrees with
  `<별표가지번호>`)
- empty annex title
- empty normalized annex content

Verification / smoke:

- `python -m compileall src/ingest`
- `PYTHONPATH=src python -m pytest tests/ingest/test_annexes.py -q`
- Docker Compose DB smoke when `.env` and the database service are
  available:
  - clean Phase-1 ingest inserts 2 `legal_documents`
  - inserts 240 `structure_nodes`
  - inserts 5 `annexes`
  - inserts 21 `annex_attachments` rows for HWP/PDF/image references
  - rerun skips unchanged docs without duplicating annexes

## References

- `docs/decisions/ADR-001-split-annexes-and-forms.md`
- `docs/decisions/ADR-003-chunks-fk-shape.md`
- `docs/decisions/ADR-010-phase-1-ddl-freeze.md`
- `docs/decisions/ADR-011-raw-api-xml-retention.md`
- `docs/decisions/ADR-013-amendment-tracking.md`
- `docs/legal-erd-draft.md` — `annexes` table definition
- `migrations/001_statute_tables.sql` — pre-ADR-014 frozen `annexes` DDL
- `data/raw/014159/277417.xml` — Phase-1 Decree sample with 5 annexes
