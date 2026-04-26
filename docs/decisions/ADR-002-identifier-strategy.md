# ADR-002 — `BIGINT IDENTITY` PK + natural-key `UNIQUE` for statute tables

- **Status**: Accepted
- **Date**: 2026-04-25
- **Context layer**: Statute (성문규범) ERD
- **Resolves**: TODO-4 in `docs/legal-erd-draft.md`
- **Plan file**: `~/.claude/plans/quizzical-scribbling-scone.md`
- **Related principles**: phase-1-progress.md §5 design principles #5 (multi-source
  by design) and #9 (idempotent indexing)
- **Depends on**: a chunks-table FK shape decision drafted as **ADR-003 (Proposed)**.
  ADR-002's Rationale #2 ("uniform `BIGINT` FK shape into chunks") and the
  rejection of Option C are conditional on whichever shape ADR-003 picks.
  All three candidates in ADR-003 (polymorphic, split FK columns, split
  chunks tables) want a single non-composite BIGINT reference column per
  source — so the **decision** stands across all three; the **reasoning
  weight** shifts only between principles #5, #9, and locality depending on
  the outcome

## Context

Five statute tables (`legal_documents`, `structure_nodes`,
`supplementary_provisions`, `annexes`, `forms`) need a primary-key strategy.
The decision is upstream of DDL writing, the ingestion script, and the
chunks-table FK shape.

A single, consistent strategy across the five **statute-scope** tables keeps
their FK shape uniform regardless of which chunks-table FK pattern ADR-003
ultimately picks (polymorphic `source_id`, split columns with one FK per
source table, or split chunks tables — see ADR-003). Mixed PK shapes within
the statute family would force a chunks reference into either a composite or
a text-encoded column, which all three candidates would prefer to avoid.
Whether the same uniform-`BIGINT` argument extends to future non-statute
categories (judicial, interpretive, practical, academic) is a
related-but-separate decision — see "Consequences" for how that is left
open.

## Decision

Every statute table uses:

- **PK**: `BIGINT GENERATED ALWAYS AS IDENTITY` (a surrogate, sequence-backed
  bigint).
- **UNIQUE constraint**: a separate constraint on the API-native natural key.

Per-table specifics:

| Table | PK | UNIQUE constraint | Natural-key source |
|-------|----|-------------------|--------------------|
| `legal_documents` | `doc_id BIGINT IDENTITY` | `UNIQUE (mst)` | `<법령일련번호>` |
| `structure_nodes` | `node_id BIGINT IDENTITY` | `UNIQUE (doc_id, node_key)` | `<조문단위 조문키>` |
| `supplementary_provisions` | `provision_id BIGINT IDENTITY` | `UNIQUE (doc_id, provision_key)` | `<부칙단위 부칙키>` |
| `annexes` | `annex_id BIGINT IDENTITY` | `UNIQUE (doc_id, annex_key)` | `<별표단위 별표키>` (E suffix) |
| `forms` | `form_id BIGINT IDENTITY` | `UNIQUE (doc_id, form_key)` | `<별표단위 별표키>` (F suffix) |

`legal_documents.law_id` (법령ID) is deliberately **not** in any UNIQUE
constraint, because it is shared across versions of the same law. When Phase 2
temporality is activated and multiple versions can co-exist, `law_id` will
become non-unique. The version-specific natural key is `mst`.

## Options considered

| Option | PK type | Natural key | Verdict |
|--------|---------|-------------|---------|
| A | `BIGINT IDENTITY` only | none | rejected — no upsert path; ingestion needs lookup-then-insert, racier |
| B | `UUID v4` only | none | rejected — 2× storage, v4 randomness fragments B-tree reads, no upsert path |
| C | composite natural key as PK | embedded in PK | rejected — every FK becomes composite; constrains chunks-table FK shape (see Dependencies) |
| **D** | **`BIGINT IDENTITY` PK + natural-key `UNIQUE`** | **separate UK** | **accepted** |
| E | ULID / Snowflake / Sonyflake (sortable 128-bit or 64-bit IDs) | optional UK | rejected — these designs solve coordination-free generation across distributed writers; under a single-Postgres, single-writer ingestion model the extra width (ULID 16 bytes) and the need for an extension or custom function deliver no offsetting benefit. Re-examine if Phase 4+ introduces federation |

## Why D over A/B/C

1. **Idempotent ingestion (principle #9)** — every row supports
   `INSERT … ON CONFLICT (natural_key) DO UPDATE … RETURNING …`. The actual
   workflow is **parent-first**: upsert `legal_documents` with `RETURNING
   doc_id`, then upsert children (`structure_nodes`, `annexes`, etc.) using
   that `doc_id` in their composite natural keys. So it is not literally
   "one statement total" — it is one upsert per row, no lookup-then-insert
   round-trip per row, and no separate dedup logic. A and B (no natural UK)
   would require a `SELECT` before each `INSERT` to detect re-runs, which is
   both racier and more code.

2. **Uniform `BIGINT` FK shape into chunks (principle #5)** — chunks reference
   five statute tables today, plus future categories. Whatever shape ADR-003
   picks (polymorphic `source_id`, split FK columns, or split chunks tables),
   each of those candidates wants every source PK to be a single
   non-composite column of the same width — composite PKs (Option C) would
   force a composite reference column or a string-encoded fallback in any of
   them. This rationale is therefore conditional on ADR-003's outcome but
   resilient to which of its three options wins.

3. **B-tree FK lookup locality after vector search** — pgvector indexes the
   embedding column itself; the source identifier is a payload column riding
   along. After an HNSW/IVFFlat lookup returns a list of `source_id` values,
   those IDs hit the **B-tree FK index** on the source tables. Sequential
   `BIGINT` keeps that lookup buffer-cache-friendly; UUID v4's randomness
   fragments the B-tree reads. Negligible at Phase-1 scale, real at Phase-4.

4. **Reversible later** — adding an `external_uuid uuid UNIQUE` column on top
   of an existing `BIGINT` PK is a non-destructive migration. Going the other
   direction — collapsing UUIDs into bigints — is destructive.

## Trade-off accepted

PK values are **not** portable across DB rebuilds. If we drop and re-ingest,
`BIGINT` IDs may differ between runs.

Mitigations:

- The **natural key** is portable, so chunks-to-source linkage can always be
  re-derived via the UK after a rebuild.
- Chunks get rebuilt on every embedding refresh anyway, so the chunks-side
  FK values (under any of ADR-003's candidate shapes) are never
  authoritative across rebuilds.

## What was checked vs. what is still open

A spot-check against `docs/api-samples/` confirmed that the **structural
assumptions** behind each UNIQUE constraint hold within the inspected payloads:

| Constraint | Sample inspected | Result |
|------------|------------------|--------|
| `(doc_id, node_key)` | Act (law-228817), 20 nodes | no within-doc collisions |
| `(doc_id, node_key)` | Decree (law-277417), 17 nodes | no within-doc collisions |
| `(doc_id, annex_key)` | Decree, 5 annexes | no within-doc collisions |
| `(doc_id, provision_key)` | Decree, 6 supplementary provisions | no within-doc collisions |

This is best read as "the API contract is consistent with the schema's
assumptions for these documents," **not** as broad validation. Within-document
uniqueness of API-native keys is essentially an API contract; if the
법제처 response broke it, that would be an API bug, not a modeling problem
on our side.

The hypotheses that are actually at risk and **not** validated by the above:

1. **`mst` global uniqueness across many laws** — the inspection covered
   exactly two `mst` values (228817 act, 277417 decree). The API documents
   `법령일련번호` as a per-version identifier, but cross-statute uniqueness
   has not been stress-tested at scale.
2. **E/F suffix discipline in the 별표키 namespace** — the schema relies on
   the source XML never producing two `별표단위` rows that share number,
   branch number, and suffix within a single document. The two inspected
   documents have either only `E` or only `F` in clusters; we have not seen
   a single document that mixes them densely. Worth a sanity grep when more
   laws are ingested.
3. **`mst` stability across amendments** — once Phase 2 temporality is
   active and amendment history accumulates, can `(mst)` continue to serve
   as the sole UNIQUE constraint on `legal_documents`? Likely yes (each
   `법령일련번호` is per-version), but this is the load-bearing question for
   TODO-5 to answer.

These are tracked as verification work, not as blockers for this ADR.

## Consequences

- DDL will use `GENERATED ALWAYS AS IDENTITY` rather than `BIGSERIAL`
  (SQL-standard, recommended Postgres ≥ 10).
- The ingestion script can use `INSERT ... ON CONFLICT (natural_key) DO UPDATE
  ...` for every table. No separate dedup logic required.
- For Phase 1 statute scope, every chunks-side FK into a statute table will
  be `BIGINT` (the exact column name and shape depend on ADR-003 — single
  polymorphic `source_id`, dedicated `structure_node_id` / `annex_id`
  columns, or per-source chunks tables). Whether the same PK strategy
  applies to future non-statute ERDs (judicial, interpretive, practical,
  academic) is **open** — it is *recommended* on the same grounds, but
  each category will be re-confirmed when its own ADR is drafted.
- TODO-5 (amendment retention policy) may add a *second* UNIQUE constraint to
  some tables (e.g., `(law_id, effective_at)` on `legal_documents`) but does
  not invalidate the constraints established here.

## References

- `docs/legal-erd-draft.md` — TODO-4 resolution block, Mermaid diagram, entity
  description tables
- `~/.claude/plans/quizzical-scribbling-scone.md` — full plan with options
  analysis
- `docs/api-samples/law-228817-중대재해처벌법.xml`,
  `docs/api-samples/law-277417-중대재해처벌법시행령.xml` — sample XML used
  to spot-check the structural assumptions described in "What was checked
  vs. what is still open"
- `docs/decisions/ADR-003-chunks-fk-shape.md` (Proposed) — decides the
  chunks-side reference shape this ADR depends on
