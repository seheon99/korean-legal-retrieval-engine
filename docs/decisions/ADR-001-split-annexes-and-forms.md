# ADR-001 — Split annexes and forms into separate tables

- **Status**: Accepted
- **Date**: 2026-04-25
- **Context layer**: Statute (성문규범) ERD
- **Resolves**: TODO-1 in `docs/legal-erd-draft.md`
- **Related**: DA #2 (phase-1-progress.md §8) — appendices are part of the statute, not a separate top-level category

## Context

The 법제처 OpenAPI returns annexes (별표) and forms (서식) under a single XML
parent element (`<별표>`), with a discriminator field `<별표구분>` whose values
are `별표` or `서식`. The original ERD sketch did not address them, and an
earlier framing left a single TODO asking whether to bundle both into one
`appendices` table or keep them apart.

The decision matters because:

- **Annexes carry substantive provisions** delegated from the main body
  (penalty schedules, scope qualifiers, occupational-disease lists). User
  queries need to match annex content directly. Annexes must be a first-class
  source for the search index.
- **Forms are blank templates** — report forms, application forms,
  confirmation forms. The retrieval question is "where can I find form X?",
  answered by metadata + a download link, not by matching body text.

Bundling them into one table forces a `content_text NULL` pattern that bleeds
into both schema and application code, and risks degrading search quality if
form bodies leak into the index.

## Decision

Split annexes and forms into two separate tables:

- `annexes` — full schema including `content_text`, `content_format`, file
  attachments. **Is** a chunk source.
- `forms` — metadata + file attachments only, **no** `content_text` column.
  **Is not** a chunk source.

Both tables share file-attachment columns (HWP, PDF, image filenames + URLs)
because the API returns the same structure for both. The `별표구분` value at
parse time determines which table a row goes into; the `별표키` suffix (`E`
for annex, `F` for form) gives a secondary signal.

## Empirical basis (verified 2026-04-25)

API inspection of two real XML responses:

| Question | Finding |
|----------|---------|
| Are annexes inline text or attachment-only? | **Inline** — `<별표내용>` CDATA contains full text. HWP/PDF/GIF are supplementary |
| Are forms inline text or attachment-only? | **Inline too** — but body is ASCII box-drawing rendering of form layout |
| Is there a discriminator field? | Yes — `<별표구분>` with values `별표` / `서식` |
| Is the 별표키 distinct? | Yes — annexes end in `E` (e.g., `000100E`), forms in `F` (e.g., `000100F`) |
| Phase 1 scope volumes | 중대재해처벌법 시행령: 5 annexes, 0 forms. 산안법 시행규칙 (cross-reference): 27 annexes, 111 forms |

The original framing assumed forms would have empty bodies. The empirical
finding is more nuanced: form bodies are **present** but they are ASCII
box-art renderings of form layouts that would actively harm retrieval quality
if indexed. The decision to exclude form bodies from the search index is
therefore on **retrieval-quality grounds**, not on data-availability grounds.

## Consequences

- `chunks.source_id` references either `structure_nodes.node_id` or
  `annexes.annex_id`; never `forms.form_id`. The chunks-table FK design
  treats forms as out-of-band metadata reachable only by document-level
  search.
- The Document Parsing Pipeline branches on `<별표구분>` at ingest time and
  routes to one of two tables.
- Inline `<별표내용>` text is sufficient for indexing in Phase 1, so HWP/PDF
  parsing is **not on the Phase-1 critical path**. Whether to invest in
  HWP/PDF parsing later (e.g., for higher-fidelity table extraction) is
  **open** and not covered by this ADR. The HWP/PDF download URLs are
  retained on the row in case future ERD work needs them; their UI use is
  not decided here.
- A `content_format` enum on `annexes` (`prose | table | mixed`) is reserved
  as a parser-stage hint for future enhancement (e.g., table-aware chunking).
  Phase 1 does not branch on this field.

## References

- `docs/legal-erd-draft.md` — TODO-1 resolution block + `annexes` and `forms`
  table definitions
- `docs/api-samples/law-277417-중대재해처벌법시행령.xml` — primary evidence
  (5 annexes, all `별표구분=별표`)
- `docs/api-samples/` — 산안법 시행규칙 inspection (cross-reference for the
  form case; not retained because it is outside Phase 1 scope)
- `docs/phase-1-progress.md` §8, DA #2 — prior agreement that appendices are
  part of the statute
