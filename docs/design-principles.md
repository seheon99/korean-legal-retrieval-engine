# Design Principles

Durable design principles for KLRE. Originally agreed across the early
sessions; restated here as a single canonical list. Phase plans and progress
notes link here rather than restating.

1. **Interface-First** — use Python `Protocol` to define seams.
2. **Pluggable Components** — embedding model, reranker, retriever
   implementations swap without touching call sites.
3. **Everything Measurable** — explain mode, score traces, per-stage
   diagnostics. Per ADR-021, internal traces live in the fixed `diagnostics`
   block of the result envelope, not as public knobs.
4. **Temporal-Ready but Not Temporal-Active** — `effective_at`,
   `superseded_at`, `is_head` are reserved up front; cross-amendment
   resolution is later work (ADR-013, ADR-022).
5. **Multi-Source by Design** — `source_type` from day one even when only
   statutes are populated.
6. **Collection as First-Class** — corpus / collection identity is part of
   the data model, not an afterthought.
7. **Filters Not Afterthoughts** — structured filters (effective date,
   `law_id`, source kind) are first-class, not a post-search re-rank.
8. **Indexing ⊥ Retrieval** — load and indexing are separate stages from
   retrieval. (RAGFlow framing.)
9. **Idempotent Indexing** — re-running ingest on unchanged source data is a
   no-op. Verified for canonical `eflaw` ingest 2026-05-06.
10. **Explicit Over Implicit** — no inferred parentage, no inferred
    effectiveness, no inferred citations. Surface `<TBD>` / `<verify>` rather
    than guess.
11. **Query Understanding is First-Class** — Phase 2+ work; Phase 1 keeps the
    query surface legal-intent-shaped per ADR-021 without exposing raw
    retrieval knobs.
12. **Authority-Aware Retrieval** — `authority_level` and `judgment_status`
    are chunk metadata so retrieval can rank or filter by authority, not just
    similarity.
13. **Measure First, Plan Second** — no architectural decisions before the
    measurement that would justify them. The first hybrid eval is the gate
    for downstream pipeline expansion.
