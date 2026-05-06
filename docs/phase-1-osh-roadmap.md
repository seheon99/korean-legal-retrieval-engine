# Phase 1 Roadmap — SAPA + OSH Full-Family Hybrid Baseline

Date: 2026-05-06

## Summary

Phase 1 expands from a single-statute walking skeleton to a two-family
statute baseline:

- `중대재해 처벌 등에 관한 법률` family: already ingested Act + Decree.
- `산업안전보건법` family: Act + 시행령 + 시행규칙.
- Version policy: ingest both head/future-effective and effective-as-of
  `2026-05-06` slices when they differ.
- Retrieval/eval default: answer against the legally effective slice as of
  `2026-05-06`, unless the query explicitly asks for future effectiveness.
- First retrieval target: hybrid immediately — BM25 + vector + RRF +
  reranker — with `bge-m3` and KURE compared before freezing the embedding
  choice.

This is ADR-level scope expansion. The first required artifact is
[ADR-019](../decisions/ADR-019-phase-1-osh-scope.md) in `Proposed`
status. No fetch-script, parser, schema, or retrieval implementation should
ship until ADR-019 is accepted.

## Implementation Roadmap

1. **Scope ADR**
   - Draft ADR-019 to amend the old "single statute first" Phase-1 rule.
   - State that Phase 1 now covers SAPA + OSH full statutory families.
   - Keep `supplementary_provisions` and `forms` persistence-only, not
     chunk sources.
   - Keep chunk sources at `structure_nodes` and `annexes` per ADR-003 and
     ADR-005.

2. **OSH API Discovery**
   - Use law.go.kr DRF `lawSearch.do?target=law`,
     `lawSearch.do?target=eflaw`, `lawService.do?target=law`, and
     `lawService.do?target=eflaw`.
   - Discover OSH Act, 시행령, and 시행규칙 IDs/MSTs from the API; do not
     hard-code from search snippets.
   - Fetch both effective-as-of `2026-05-06` and future/head candidates.
   - Verify whether `target=eflaw` responses require raw-file path
     disambiguation beyond `data/raw/{law_id}/{mst}.xml`.

3. **Source-Ingestion Completion**
   - Complete ADR-013 supersession semantics before storing multiple
     versions for the same `law_id`.
   - Implement `supplementary_provisions` parser/populator.
   - Implement `forms` and `form_attachments` parser/populator because OSH
     시행규칙 includes forms.
   - Extend annex/form attachment retention conservatively: annex PDFs
     remain default-retained; forms are provenance-only unless a later ADR
     makes form binary retention necessary.

4. **Chunk + Hybrid Retrieval**
   - Add `chunks` with split FK columns and real FKs:
     `structure_node_id`, `annex_id`, generated `source_type`, and
     exactly-one-source CHECK.
   - Generate chunks only from effective-as-of source rows for the first
     eval corpus; keep head/future rows available for explicit future-law
     queries.
   - Build BM25 + vector candidate retrieval, RRF fusion, and
     `bge-reranker-v2-m3` reranking.
   - Compare `bge-m3` and KURE on the same seed eval set before freezing
     the embedding model and vector dimension in DDL.

## Acceptance Criteria

- ADR-019 is accepted before implementation work beyond discovery.
- OSH full family is fetched from API, retained raw, and documented with
  exact returned `law_id`, `mst`, `doc_type`, `effective_date`, and
  `is_head` / effective-slice interpretation.
- Clean DB ingest includes SAPA + OSH family without duplicate-key or
  heading-generalization failures.
- `supplementary_provisions` rows are persisted but produce no chunks.
- `forms` rows and `form_attachments` rows are persisted but produce no
  chunks.
- `chunks` contains only `structure_nodes` and `annexes`.
- Hybrid eval reports Recall@K and MRR for both `bge-m3` and KURE.

## Verification Plan

- Parser/unit tests:
  - SAPA parser tests remain green.
  - OSH Act/Decree/Rule parser tests cover doc type, headings,
    supplementary provisions, annexes, forms, and attachment references.
  - ADR-006 verification trigger covers 시행규칙 `법종구분`.

- Database tests:
  - Migrations apply in order from a clean DB.
  - New-MST ingestion marks old rows non-head and preserves
    effective-as-of queryability.
  - Chunks CHECK rejects zero-source and two-source rows.
  - `ON DELETE RESTRICT` blocks deleting a source row with chunks.

- Retrieval tests:
  - BM25 and vector retrieval each return deterministic top-k candidates.
  - RRF preserves source IDs and ranks across BM25/vector lists.
  - Reranker consumes fused candidates and emits stable ordered results.
  - Effective-as-of filtering excludes future-effective chunks by default.

## Notes And Sources

- Current repo state at planning time: migrations through
  `003_is_head_rename.sql`; SAPA Act + Decree ingested; 5 annexes and 21
  annex attachment provenance rows; PDF-only annex retention.
- law.go.kr page evidence gathered on 2026-05-06:
  - OSH Act has future-effective slices including `[시행 2026. 6. 1.]`
    and `[시행 2026. 8. 1.]`.
  - OSH Decree current page shows `[시행 2026. 3. 24.]`.
  - OSH Rule current page shows `[시행 2026. 1. 1.]` and has a
    `서식` section.
- Official DRF API docs used for the discovery plan:
  - `lawSearch.do?target=law`
  - `lawSearch.do?target=eflaw`
  - `lawService.do?target=law`
  - `lawService.do?target=eflaw`
