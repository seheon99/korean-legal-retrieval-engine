# Phase-1 Progress

Hand-off artifact for next-session recall. State + plan only — durable
reference content lives in dedicated files.

Last updated: 2026-05-07.

## Status

- **Phase-1 statute ERD**: frozen (ADR-010, 2026-04-29). Migrations through
  `004_eflaw_identity.sql` applied. ADR-013 renamed `is_current` → `is_head`;
  ADR-014 added parallel `annex_attachments` / `form_attachments`; ADR-015
  set raw-SQL migration management with a `schema_migrations` ledger; ADR-016
  / 017 / 018 cover annex binary retention and content normalization;
  ADR-020 made `target=eflaw` the canonical statute XML source.
- **Source ingest**: complete. Default Compose DB rebuilt from canonical
  `data/raw/eflaw` on 2026-05-06. Verified counts: 11 `legal_documents`,
  11,384 `structure_nodes`, 141 `supplementary_provisions`, 129 `annexes`,
  774 `annex_attachments`, 222 `forms`, 712 `form_attachments`. Idempotent
  re-run skipped all 11 source rows by hash.
- **Retrieval contract**: ADR-021 accepted 2026-05-07 — legal-intent-first,
  deterministic + hybrid, fixed envelope with `source_content_hash`,
  ambiguity / unresolved envelope, engine-owned routing, `diagnostics`
  block.
- **Graph roadmap**: ADR-022 proposed 2026-05-07 — Phase-1 graph work is a
  Layer-1 projection contract over the current ERD; no new physical graph
  infrastructure.
- **Live boundary**: retrieval baseline. See
  [phase-1-roadmap.md](phase-1-roadmap.md) for the implementation plan.

## Project identity

KLRE is a Korean legal retrieval engine — R-layer only, not full RAG. The
Phase-1 proof point is hybrid retrieval quality (Recall@K, MRR) over the
SAPA + OSH statutory baseline. Generation, query rewriting, multi-agent
routing, and orchestration frameworks remain explicitly out until retrieval
quality is measured.

For project-operating context (stack, scope, working agreements), see
[AGENTS.md](../AGENTS.md).

## Next-session task

Start the retrieval baseline: Step 1 in
[phase-1-roadmap.md](phase-1-roadmap.md#implementation-roadmap--retrieval-baseline)
(chunks migration `005_chunks.sql`).

Caveats before starting:

- Binary attachment retention metadata is reset by the DB rebuild. Text
  retrieval does not depend on it; rerun `scripts/download_annex_attachments.py`
  if durable attachment paths/checksums are needed before retrieval.
- Rule `parent_doc_id` remains an ADR-009 revisit trigger. OSH 시행규칙 is
  the first rule-bearing statute, but Act-vs-Decree parentage for rules
  needs a follow-up ADR before population.
- ADR-022 is `Proposed`. No graph schema, projection job, or reference-
  extraction work should start until it accepts.
- ADR-018 production tokenizer choice is open. Annex de-layouting currently
  runs on a reviewed Phase-1 deterministic substitute.

## Durable references

- [legal-data-categories.md](legal-data-categories.md) — 5-category taxonomy
  and Phase-1 source inventory.
- [design-principles.md](design-principles.md) — 13 design principles.
- [legal-erd.md](legal-erd.md) — ERD reference; superseded for statute
  scope by ADRs 001–020.
- Slip patterns and working agreements live in [AGENTS.md](../AGENTS.md)
  §5–§6.

## Open decisions

- **D-2** ❓: License of public-agency manuals (KOSHA guides) — which KOGL
  type?
- **D-3** ❓: License of MoE / MoLIT commentaries — which KOGL type?
- **D-4** ❓: Whether law.go.kr OpenAPI exposes terminology-mapping
  endpoints, or whether the MCP server built that data separately. Needs
  measurement.
- **D-6** ❓: Whether KLRI materials are included in Phase-1 body indexing
  (acceptance of the Type 4 gray area).
- **D-7** ❓: Academic materials — owner converts owner-supplied PDFs before
  supplying.
- **Rule `parent_doc_id`** ❓: ADR-009 follow-up for 시행규칙 Act-vs-Decree
  parentage.
- **ADR-018 tokenizer** ❓: Korean tokenizer / morphological analyzer for
  the production annex de-layout scorer.
- **Embedding model freeze** ❓: `bge-m3` vs KURE — resolved by the seed
  eval bake-off in roadmap step 5.

Resolved decisions (D-1 statute ERD scope, D-5 parsing-pipeline timing) are
not relisted; see ADR-010 and ADR-019 respectively.

## Outstanding Phase-0 inventory tasks

These remain pending and gated on the `OC` IP-whitelist constraint or on
retrieval-baseline scoping. None blocks roadmap step 1.

- **T2**: API endpoint catalog → `docs/data-sources/law-go-kr-api-catalog.md`.
- **T6-B**: Measure case-law API coverage (counts by court level, full-text
  reachability).
- **T7-A**: Reference-material inventory (MoEL, KOSHA, MoE, MoLIT) with URL
  + license notice per item.
- **T8**: Confirm whether administrative-regulation and interpretation APIs
  exist (Phase 2+ candidates).
- **T9**: Terms-of-use review (law.go.kr ToS, redistribution, attribution).
- **T10-A**: Document Phase-1 data scope (`docs/phase-1-scope.md`).
- **T11-A** 🔶: Phase-1 raw-data dump for non-statutory sources.
- **T15**: Inventory Criminal Code articles cited by the MoEL commentary.
- **T16**: License-typed material classification table.
- **T17**: Metadata-collection strategy for copyright-strict materials.
- **T18**: Measure law.go.kr terminology API directly.
- **T19**: Investigate KOSHA safety-and-health terminology resources.

## Phase-2 follow-up parking lot

Recorded at the boundary; separate ADRs at the time:

- Drop `sort_key` column per ADR-012 §Consequences (redundant with tagless
  `node_key`).
- Migration runner script around ADR-015's raw SQL + `schema_migrations`
  convention.
- Packaging (`pyproject.toml`) when host-side Python work is needed beyond
  Docker.

## Change log

The detailed v1.0–v1.19 entries (initial artifact through canonical
SAPA + OSH source-ingest verification) are preserved in git history; the
narrative for each change lives in the corresponding `docs/sessions/*.md`
note and ADR.

- **v2.0 (2026-05-07)** — Aggressive compression. Durable reference content
  moved into `legal-data-categories.md` and `design-principles.md`. Slip
  patterns and working agreements consolidated in `AGENTS.md`. Status,
  next-session task, open decisions, and outstanding Phase-0 tasks
  retained. Retrieval baseline becomes the live boundary. ADR-021
  acceptance and ADR-022 proposal recorded.
- v1.19 (2026-05-06): default Compose DB rebuilt from canonical
  `data/raw/eflaw`; counts verified at 11 / 11,384 / 141 / 129 / 774 /
  222 / 712.
- v1.18 (2026-05-06 night): canonical SAPA + OSH source ingestion verified
  end-to-end; ADR-013 supersession lifecycle implemented.
- v1.17 (2026-05-06 night): ADR-006 ministry-prefixed `*부령` normalization
  to canonical DB `부령`.
- v1.14 / v1.15 (2026-05-06): ADR-020 accepted and executable slice landed
  (migration `004_eflaw_identity.sql`, canonical `eflaw` fetches, parser
  discovery/source-url support, `(law_id, mst, effective_date)` idempotency).
- v1.10 / v1.11 (2026-05-06): ADR-013 rename migration landed
  (`003_is_head_rename.sql`); ADR-019 expanded Phase-1 to SAPA + OSH.
- v1.5 / v1.6 / v1.7 / v1.8 / v1.9 (2026-05-05): ADR-014 annex ingestion
  landed; ADR-015 raw-SQL migration management accepted; ADR-016 binary
  retention (HWP/PDF/image); ADR-017 PDF-default-with-HWP-fallback;
  ADR-018 annex content de-layout normalization.
- v1.3 / v1.4 (2026-05-04): `structure_nodes` parser depth landed; ADR-013
  amendment-tracking, ADR-014 annex-ingestion accepted.
- v1.2 (2026-05-03): ADR-009 population rule landed and DB-verified;
  idempotent re-ingest landed; ADR-012 keying convention accepted.
- v1.1 (2026-04-29): Phase-1 statute ERD frozen via ADR-010
  (`migrations/001_statute_tables.sql`).
- v1.0: initial artifact (compressed agreements).
