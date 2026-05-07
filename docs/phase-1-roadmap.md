# Phase-1 Roadmap — SAPA + OSH Hybrid Retrieval Baseline

Last updated: 2026-05-07

## Phase-1 goal

Build the SAPA + OSH statutory baseline from canonical `eflaw` source rows
through the first hybrid retrieval evaluation. The proof point is
quantitative retrieval quality (Recall@K, MRR), not ingestion polish.

Source ingestion is complete. Retrieval is the live work.

For the legal-intent retrieval contract this baseline must satisfy, see
[decisions/ADR-021-retrieval-operation-contract.md](decisions/ADR-021-retrieval-operation-contract.md).
For Phase-1 statutory scope, see
[decisions/ADR-019-phase-1-osh-scope.md](decisions/ADR-019-phase-1-osh-scope.md).

## Status snapshot

| Layer | State |
| ---- | ---- |
| Statute ERD freeze | ✅ ADR-010, migrations through `004_eflaw_identity.sql` |
| Canonical raw XML store | ✅ `data/raw/eflaw/{law_id}/{mst}/{efYd}.xml` (ADR-011 / ADR-020) |
| SAPA + OSH source ingest | ✅ Default Compose DB rebuilt 2026-05-06 |
| Source-table population | ✅ 11 documents · 11,384 structure_nodes · 141 supp prov · 129 annexes · 774 annex attachments · 222 forms · 712 form attachments |
| Retrieval contract | ✅ ADR-021 accepted 2026-05-07 |
| Graph roadmap | 🔶 ADR-022 proposed (Phase-1 = Layer-1 projection contract over current ERD) |
| Chunks migration | ⏸️ Pending |
| Hybrid retrieval pipeline | ⏸️ Pending |
| First eval | ⏸️ Pending |

## Open Phase-1 prerequisites

These are not on the retrieval critical path but should be resolved at the
earliest meaningful boundary:

- **Binary attachment retention rerun.** The DB rebuild reset
  `stored_file_path`, `checksum_sha256`, and `fetched_at` on
  `annex_attachments` and `form_attachments`. Local files are still on disk;
  rerun `scripts/download_annex_attachments.py` if durable attachment
  metadata is needed before retrieval. Text retrieval from
  `structure_nodes.content_text` and `annexes.content_text` does not depend
  on this.
- **ADR-009 follow-up for Rule `parent_doc_id`.** OSH 시행규칙 is the first
  rule-bearing statute. Act-vs-Decree parentage for rules needs a follow-up
  ADR before population.
- **ADR-018 production tokenizer.** Annex de-layouting currently runs on a
  reviewed Phase-1 deterministic substitute. Pick the Korean tokenizer /
  morphological analyzer before broadening the scorer.
- **ADR-022 acceptance** before any graph schema, projection job, or
  reference-extraction work.

## Implementation roadmap — retrieval baseline

The numbered steps are sequential.

1. **Chunks migration.**
   Add `migrations/005_chunks.sql` per ADR-003 / ADR-005:
   - Split FK columns `structure_node_id`, `annex_id` (real FKs to source
     tables; `ON DELETE RESTRICT`).
   - Generated `source_type` column over the FK columns.
   - Exactly-one-source CHECK; zero-source and two-source rows must be
     rejected at the DB level.
   - Vector dimension placeholder pending the embedding-model decision in
     step 5; freeze before any chunk insert.
   - License metadata fields (`license_type`, `allowed_uses`) for the
     authority/license-aware design principle.
   - `source_content_hash` column tracking the source row's `content_hash`
     for the ADR-021 cache/eval keying rule.

2. **Chunk generation.**
   Generate chunks only from `structure_nodes` and `annexes`.
   `supplementary_provisions` and `forms` remain persistence-only. Default
   the generation slice to legally-effective-as-of `2026-05-06`
   (`effective_at <= '2026-05-06' < superseded_at`, with `superseded_at IS
   NULL` open-ended) per ADR-013. Keep head/future rows available for
   explicit future-law queries; do not chunk them by default.

3. **Deterministic retrieval surface.**
   Resolve known citations to a unique `(law_id, mst, effective_date)`-scoped
   source row across `structure_nodes`, `annexes`,
   `supplementary_provisions`, `forms`, and binary attachments per
   ADR-021 §1. Return the ADR-021 envelope on success and the
   ambiguous / unresolved envelope (status, parsed fragments, reason code,
   candidate list, non-authoritative diagnostics) on failure. Out-of-corpus
   `law_id` returns `unresolved` with reason code `out-of-corpus`.

4. **BM25 baseline.**
   `bm25s` over chunk text. Deterministic top-k internal candidate list.
   Evidence-list shape per ADR-021: bounded length, engine-ranked,
   deduplicated by `(source table, source row, source_content_hash)`.

5. **Vector baseline + embedding bake-off.**
   pgvector ANN. Run the same seed eval against `bge-m3` and KURE on the
   identical chunk corpus; freeze the embedding model and vector dimension
   in DDL only after the bake-off. Publish Recall@K and MRR for both before
   choosing.

6. **RRF fusion.**
   Reciprocal Rank Fusion over BM25 and vector candidate lists. Original
   query weighted 2x per the QMD pattern (the **original** query, not an
   expansion). Query expansion itself is deferred to Phase 3.

7. **Reranker.**
   `bge-reranker-v2-m3` over fused candidates. Stable ordered output.

8. **Operation routing.**
   Per ADR-021: engine-owned routing between deterministic retrieval, hybrid
   evidence retrieval, and mixed citation-plus-concept composition. Mixed
   inputs first resolve the cited anchor, then run hybrid retrieval
   constrained or boosted by it; composition mode (`anchor-filter` vs
   `anchor-boost`) reported in routing diagnostics.

9. **Result envelope packaging.**
   Every valid result carries: canonical citation text;
   `(law_id, mst, effective_date)`; `effective_at`, `superseded_at`,
   `is_head` (ingestion-lineage, not legal effectiveness); `source_url`
   shaped per ADR-020 (`target=eflaw`, `MST`, `efYd`); `source_content_hash`;
   source table and row ID; hierarchy path. Hybrid results add rank/score
   diagnostics in a fixed `diagnostics` block.

10. **Seed eval set + harness.**
    Author a Phase-1 seed eval covering both operation tracks:
    - deterministic citation-resolution accuracy (exact-match against the
      resolved source row);
    - hybrid evidence Recall@K and MRR.
    Eval rows key against `(source identity, source_content_hash)`.

11. **First eval report.**
    Recall@K and MRR for both operation tracks, BM25-only / vector-only /
    fused / fused+rerank ablations, and `bge-m3` vs KURE for the embedding
    track.

## Acceptance criteria

- Migrations `001`-`005` apply cleanly against an empty database.
- `chunks` rejects zero-source and two-source rows at the DB level.
- `chunks` contains only `structure_nodes` and `annexes` source rows.
- `supplementary_provisions`, `forms`, `form_attachments`, and
  `*_attachments` are populated but never become chunk sources.
- Deterministic retrieval resolves SAPA + OSH citations to unique source
  rows and returns ADR-021's success envelope.
- Deterministic retrieval returns the ADR-021 ambiguous / unresolved
  envelope on failure rather than a best-effort semantic match.
- Out-of-corpus `law_id` returns `unresolved` with reason code
  `out-of-corpus`.
- Hybrid retrieval returns engine-ranked, deduplicated evidence objects
  carrying the full ADR-021 envelope plus a fixed `diagnostics` block.
- Mixed citation-plus-concept inputs return both the resolved anchor and
  the evidence list (or a typed unresolved envelope) and report the
  composition mode in routing diagnostics.
- Effective-as-of filtering excludes future-effective rows by default;
  head/future-effective queries require an explicit mode.
- First eval report includes Recall@K and MRR for both operation tracks
  and for `bge-m3` and KURE.

## Verification plan

- **Migration tests**: clean-DB apply, FK reject of orphan inserts,
  exactly-one-source CHECK reject of zero-source and two-source rows.
- **Chunking tests**: `structure_nodes` + `annexes` rows produce stable
  chunks; `supplementary_provisions` and `forms` produce zero chunks;
  re-running chunk generation against an unchanged source slice is
  idempotent.
- **Deterministic retrieval tests**: known citations resolve to expected
  rows; ambiguous citations return the ambiguous envelope; out-of-corpus
  citations return `unresolved` with reason code `out-of-corpus`.
- **Hybrid retrieval tests**: BM25-only, vector-only, fused, and
  fused+rerank each emit deterministic evidence-object lists; dedup by
  `(source table, source row, source_content_hash)` rolls 1:N chunk-from-
  row results into a single evidence object with chunk-level diagnostics.
- **Effective-date tests**: default slice excludes
  `effective_at > 2026-05-06` rows; explicit head mode admits them.
- **Eval harness**: Recall@K, MRR, and per-track accuracy reported with
  source-content hashes pinned per eval row.

## Out of scope (Phase 1)

- Generation / answer synthesis. Retrieval engine only.
- Query Rewriting (Phase 3).
- Multi-agent routing, LLM router, orchestration frameworks.
- LangChain, LlamaIndex, or any pipeline framework.
- Non-statutory categories (judicial, interpretive, practical, academic) at
  the chunk-source level. Their ERDs may ship as parallel work but do not
  block this baseline.
- Physical graph storage, projection jobs, or graph DB selection (ADR-022
  Phase-1 graph work is a contract over the current ERD only).
- Reference resolution (ADR-022 Layer 2), definition modeling (Layer 3),
  legal semantic graph (Layer 4).
- Cross-amendment continuity / "same provision across versions" linkage.

## References

- ADRs: [001](decisions/ADR-001-split-annexes-and-forms.md) ·
  [003](decisions/ADR-003-chunks-fk-shape.md) ·
  [005](decisions/ADR-005-supplementary-provisions-not-chunk-source.md) ·
  [010](decisions/ADR-010-phase-1-ddl-freeze.md) ·
  [012](decisions/ADR-012-structure-nodes-keying-and-sort.md) ·
  [013](decisions/ADR-013-amendment-tracking.md) ·
  [019](decisions/ADR-019-phase-1-osh-scope.md) ·
  [020](decisions/ADR-020-effective-law-raw-identity.md) ·
  [021](decisions/ADR-021-retrieval-operation-contract.md) ·
  [022](decisions/ADR-022-graph-modeling-roadmap.md) (proposed).
- Durable references:
  [legal-data-categories.md](legal-data-categories.md) ·
  [design-principles.md](design-principles.md).
