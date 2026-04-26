# ADR-003 — Chunks-table FK shape across multi-source retrieval

- **Status**: **Accepted** (revision 2; accepted 2026-04-26)
- **Date**: 2026-04-25 (initial draft); revised and accepted 2026-04-26
- **Context layer**: Search-index layer (chunks)
- **Triggers**: ADR-002's DA pass surfaced that the chunks FK shape was
  implicitly assumed (polymorphic `(source_type, source_id BIGINT)`) without
  ever being decided. ADR-002's Rationale #2 leans on whatever this ADR
  decides.
- **Related**: phase-1-progress.md §5 design principle #5 (multi-source by
  design); ADR-001 (annexes are a chunk source, forms are not); ADR-002
  (BIGINT PKs across statute tables — outcome of this ADR will not change
  ADR-002's decision but will reframe its rationale)
- **Open upstream question**: chunking granularity (1:1 vs 1:N vs cross-source
  span) is treated as an explicit assumption in this ADR (see "Granularity
  assumption" below). If that assumption changes, this ADR has to be
  re-opened. A dedicated chunking-granularity ADR may eventually supersede
  this assumption block.

## Granularity assumption

This ADR explicitly assumes **1:N chunks-per-source** (one source row maps to
one or more chunks; a chunk never spans multiple source rows). Concretely:

- One `structure_nodes` row can produce N chunks if the article body is too
  long for the embedding window. A `chunk_index` column on `chunks` will
  carry the within-source ordinal.
- One `annexes` row can produce N chunks similarly (long annex tables get
  split).
- A chunk **never** combines content from two source rows.

The granularity-space alternatives:

| Granularity | Implication for ADR-003 |
|-------------|------------------------|
| 1:1 (Option X) | chunks is essentially a view over source — the case for a separate `chunks` table weakens, but the design here still works |
| **1:N (Option Y) — assumed here** | separate table strongly justified, requires `chunk_index` and `chunks.source` FK |
| Cross-source span (Option Z) | a single chunk references multiple sources — the "exactly one FK non-null" CHECK in this ADR **fails**, and the ADR must be rewritten |

If Option Z is ever needed (e.g., for cross-article semantic units), the
chunks model fundamentally changes — likely to a many-to-many `chunks ↔
source` join table. That is out of scope here; if it happens, this ADR is
explicitly superseded.

## Context

The search index layer is a single `chunks` table that holds embeddings for
text drawn from multiple source families: statute (the body in
`structure_nodes` plus `annexes`), and — in later phases — judicial,
interpretive, practical, and academic. Every chunk needs to point back to a
specific source row so that retrieval results can resurface the original
context (statute article, annex section, case holding, commentary paragraph,
etc.).

Four FK shapes are live:

1. **Polymorphic** — `(source_type TEXT, source_id BIGINT)`, no FK
   constraints. Application code (or SQL triggers) enforces integrity.
2. **Split FK columns + real FKs** — one `chunks` table with one nullable
   BIGINT FK column per source table (`structure_node_id`, `annex_id`,
   `case_section_id`, …), plus a CHECK constraint enforcing "exactly one
   non-null." Real `REFERENCES` clauses on every FK column.
3. **Split tables** — separate `statute_node_chunks`, `annex_chunks`,
   `judicial_chunks`, … each with a real FK to its single source table.
4. **Split FK columns without FK constraints** — same shape as Option 2 but
   with no `REFERENCES` clauses. Integrity is application-level. Justified
   by the observation that chunks are derived/disposable data, rebuilt on
   every embedding refresh, so DB-enforced referential integrity earns less
   than it would on durable data.

The choice affects: query shape (single index vs UNION across tables),
referential integrity (DB-enforced vs app-enforced), schema evolution cost
(adding a new source family), and the chunks-side cost of hybrid retrieval
(BM25 + vector + RRF over the *unioned* result set).

## Recommendation: **Option 2 — split FK columns with real FKs**

Use one `chunks` table with one BIGINT FK column per source table, real
`REFERENCES` clauses, a `chunk_index` column for the 1:N fan-out, and a
**generated** `source_type` discriminator that is structurally consistent
with the populated FK column.

```sql
chunks (
  chunk_id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

  -- statute family (one nullable BIGINT FK per source table)
  structure_node_id     BIGINT REFERENCES structure_nodes(node_id) ON DELETE RESTRICT,
  annex_id              BIGINT REFERENCES annexes(annex_id)        ON DELETE RESTRICT,
  -- (future: case_section_id, interpretation_section_id, commentary_section_id, …)

  -- the discriminator is generated, not user-supplied — disagreement impossible
  source_type           TEXT GENERATED ALWAYS AS (
                          CASE
                            WHEN structure_node_id IS NOT NULL THEN 'statute_node'
                            WHEN annex_id          IS NOT NULL THEN 'statute_annex'
                            -- … per future column
                          END
                        ) STORED,

  chunk_index           INT NOT NULL,    -- 0-based ordinal within the source row
  text                  TEXT NOT NULL,
  embedding             VECTOR(1024) NOT NULL,
  -- … other shared columns (authority_level, license, …)

  CHECK ( (structure_node_id IS NOT NULL)::int +
          (annex_id          IS NOT NULL)::int = 1 )    -- exactly one source FK
)
```

Two design notes worth highlighting:

- **`source_type` is a `GENERATED ALWAYS … STORED` column.** Manual + CHECK
  for discriminator agreement was the original draft; switching to generated
  removes the second CHECK, makes disagreement structurally impossible, and
  removes any "which is the source of truth" ambiguity.
- **`ON DELETE RESTRICT` is intentional.** Source deletions in Phase 1 are
  rare; the operational friction of "delete the chunks first" is the price
  for early bug detection during ingestion development. See Option 4
  rejection below for the explicit reasoning.

## Why split-columns-with-FK over the other three options

### vs. Option 1 (polymorphic)

- **DB-enforced integrity vs application-level integrity.** Polymorphic
  relies entirely on application code (or SQL triggers) to ensure
  `(source_type='statute_node', source_id=42)` actually points at a real
  row. Triggers are possible but more involved than a real FK clause.
  Split-columns moves most integrity into DB constraints (FK + CHECK)
  without needing trigger maintenance.
- **Width cost is in the noise — but for the TOAST reason, not the NULL
  bitmap.** Each chunks row already carries a `VECTOR(1024)` embedding (~4 KB)
  and a `text` body that can be several KB. The row TOASTs out of the inline
  page regardless. Adding 5 nullable `BIGINT` columns does not change inline
  fit and does not push the row across any new threshold. (The earlier draft
  cited "NULL is a 1-bit flag in the row header," which oversimplified
  Postgres NULL bitmap mechanics — the bitmap is allocated whenever any
  column is null, and its size scales with column count. It is small but
  not literally 1 bit.)
- **Query plans are cleaner.** `JOIN structure_nodes USING (node_id)` is
  trivially indexable; `JOIN ... ON source_id = node_id AND source_type =
  'statute_node'` is harder to keep tight without partial indexes.

### vs. Option 3 (split tables)

The strongest argument against split tables is in retrieval mechanics, not
in schema ergonomics:

- **BM25 IDF must be computed against a single inverted index.** BM25's
  document-frequency term is global to the index; if statutes and cases
  live in different `bm25s` indexes, their scores are computed against
  different document statistics and are not directly comparable. UNION-then-
  normalize either degrades quality (heuristic score normalization) or
  forces a re-index across the union (defeating the per-table separation).
- **RRF requires rank comparability within a single ranked list.** RRF takes
  the rank of each document within each retrieval list and fuses by `1 /
  (k + rank)`. If "rank 5 in case_chunks" and "rank 5 in statute_chunks"
  come from differently-sized indexes with different score distributions,
  the rank values are not on the same scale. Producing a single ranked list
  in the first place requires a single chunks population.
- **One vector index, not N.** Each split chunks table needs its own HNSW
  or IVFFlat index, with separate tuning, separate maintenance, and N times
  the index-rebuild cost during embedding refreshes.
- **Schema evolution is local.** Adding a new source family is "add a
  column + a FK + an entry in the CHECK constraint + an entry in the
  generated `source_type` expression," not "create a new chunks table +
  replicate every shared column + extend the retrieval UNION."

### vs. Option 4 (split FK columns without FK constraints)

This is the closest competitor to the recommended option, and the one whose
rejection most needs to be in writing.

The argument **for** Option 4: chunks are derived data. ADR-002 already
concedes that chunks are not authoritative across DB rebuilds (they get
re-embedded). RAGFlow and similar systems deliberately keep chunks loosely
coupled to source. A real FK enforces a constraint that arguably matters
less on disposable data than on durable data.

`ON DELETE CASCADE` makes the FK redundant: source deletion takes chunks
with it, but the next embedding refresh would have rebuilt them anyway.
`ON DELETE RESTRICT` blocks source deletion until chunks are dropped —
operationally painful when statutes are repealed or amended in batch.

The argument **against** Option 4 (and why Option 2 wins by a thin margin):

- **Ingestion development is the high-bug-rate phase.** During Phase 1
  ingestion-script development, the FK constraint catches bugs at insert
  time (typo in column name, off-by-one in source_id mapping, wrong table
  written to) instead of letting them propagate into corrupt chunks that
  pass tests but break retrieval quality silently. The catch-rate value is
  highest exactly when the system has the least production-history to lean
  on.
- **`ON DELETE RESTRICT` friction is low in Phase 1.** Source deletions
  happen on amendment events (rare) and on test-fixture rebuilds (where
  truncating chunks-first is trivial). It is not a hot-path operation.
- **Reverting Option 2 → Option 4 is non-destructive.** If RESTRICT
  friction becomes painful later, dropping the `REFERENCES` clauses is a
  one-line migration. Going the other direction — adding FKs after chunks
  has accumulated dangling references — requires a data-cleanup pass first.

So: keep real FKs in Phase 1, treat the trade-off as explicitly recorded
here, and re-examine if operational friction surfaces.

## Implications for ADR-002

- ADR-002's decision (`BIGINT IDENTITY` PK + natural-key UNIQUE) **stands
  unchanged**: split-columns wants single-column BIGINT references just as
  much as polymorphic does. Option C (composite natural PK) is rejected
  in any of the four worlds.
- ADR-002's revised Rationale #2 ("uniform `BIGINT` FK shape into chunks")
  already accommodates this outcome.

## Trade-offs accepted

- **CHECK-constraint complexity grows with category count.** Each new source
  family adds a column to the `+` expression and a branch to the generated
  `source_type` expression. Tolerable for N ≤ 10. If the project ever needs
  to track 50+ source types (it will not), polymorphic becomes more
  attractive.
- **Static set of source families.** Split-columns assumes the source
  taxonomy changes by migration, not by data row. The five-category
  taxonomy in `phase-1-progress.md §2` is settled, so this is fine.
- **`ON DELETE RESTRICT` operational friction.** Source deletions require
  dropping chunks first. Acceptable in Phase 1 (rare); revisit if the rate
  of source-amendment events becomes high.
- **Granularity is assumed 1:N.** If cross-source spanning chunks (Option Z
  in the granularity space) ever become necessary, this ADR's CHECK fails
  and the chunks model has to be reworked.

## Verification once accepted

1. Sketch the chunks DDL with the CHECK constraints and the generated
   `source_type` actually written out for the Phase 1 source columns
   (`structure_node_id`, `annex_id`).
2. Confirm with a tiny test fixture that:
   - Inserting a chunk with both FK columns null fails the CHECK.
   - Inserting a chunk with two FK columns populated fails the CHECK.
   - The generated `source_type` value matches whichever FK column is
     populated, with no possibility of disagreement.
   - `ON DELETE RESTRICT` blocks a `DELETE` on a source row that has
     chunks pointing at it.
3. Verify that `WHERE source_type = 'statute_node'` plans to a clean index
   scan rather than a sequential scan with filter (a partial index or
   expression index may be needed if the planner does not inline the
   generated expression).

## References

- ADR-001 — annexes are a chunk source, forms are not
- ADR-002 — `BIGINT IDENTITY` PK + natural-key UNIQUE for statute tables
- `phase-1-progress.md` §5 — chunks metadata schema sketch (shows a
  polymorphic shape; **superseded** by this ADR)
- `phase-1-progress.md` §5 — per-category source-structure design
  (`legal_documents` + `structure_nodes`, `case_laws` + `case_sections`,
  …); informs the column list for the future per-category FK columns
