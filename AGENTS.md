# Korean Legal Retrieval Engine — Project Operating Manual

This file is loaded automatically by Claude Code at the start of every session.
Keep it short. Treat it as a senior engineer's day-1 onboarding page.

---

## 1. Project Identity

Korean Legal Retrieval Engine — **R-layer only**, not full RAG.
Dual goal: production-grade retrieval engine
Owner: Seheon — freelance backend (Kotlin/Spring · TS/NestJS · Python); SeoulTech CS; SW Maestro 14기.

**Phase 1 Statutory Baseline** (ADR-019, 2026-05-06): SAPA + OSH full statutory families.
Scope remains intentionally narrow inside 성문규범:

- `중대재해 처벌 등에 관한 법률` Act + Enforcement Decree.
- `산업안전보건법` Act + Enforcement Decree + Enforcement Rule.
  Retrieval/eval defaults to the legally effective slice as of 2026-05-06;
  head/future rows require explicit query mode.

---

## 2. Stack — Confirmed

| Layer            | Choice                            | Note                            |
| ---------------- | --------------------------------- | ------------------------------- |
| Runtime          | Python 3.11+ · FastAPI · pydantic |                                 |
| Storage          | PostgreSQL + pgvector             | unified — **not** Qdrant        |
| Sparse retrieval | bm25s                             |                                 |
| Embeddings       | KURE or bge-m3                    | Korean-tuned; choice deferred   |
| Reranker         | bge-reranker-v2-m3                |                                 |
| Forbidden        | LangChain · LlamaIndex            | direct implementation by design |

---

## 3. Architecture — Confirmed

- **Retrieval pipeline reference**: QMD pattern.
  Original query + 2 expansions → BM25 / Vector parallel → RRF (**original query gets 2x weight, not the expansion**) → bge-reranker-v2-m3.
- **Load / Indexing separation** (RAGFlow framing).
  - Source ERDs per category — kept separate.
  - `chunks` table — unified search index, references source ERDs via FK.
  - One-line summary: _sources stay separated, search is unified, FKs connect them._
- **Data categories** — 5, refined from initial 7:
  성문규범 · 사법판단 · 유권해석 · 학술자료 · 입법개정자료.
  부속참고 absorbed into 성문규범. 실무자료 handled separately.

---

## 4. Current Phase

**D-1: 성문규범 ERD — frozen.** ADR-001 through ADR-019 accepted; Phase-1 statute schema committed as `migrations/001_statute_tables.sql` (per ADR-010, 2026-04-29), with post-freeze migrations through `003_is_head_rename.sql`.

**Hard rule**: API response sample comes before schema design. We do not own the data — 법제처 does. Drawing the ERD before seeing the actual XML guarantees a rewrite.

Phase-1 schema (per ADRs 001–019):

- Five source tables: `legal_documents`, `structure_nodes`, `supplementary_provisions`, `annexes`, `forms` (ADR-002, ADR-004).
- `chunks` is the unified search index (separate migration, ships with retrieval-pipeline design). Phase-1 source FK columns are closed at two: `structure_node_id`, `annex_id` (ADR-003, ADR-005). `supplementary_provisions` is persistence-only, not a chunk source.
- `doc_type` (TEXT + CHECK over {법률, 대통령령, 총리령, 부령}) and `level` (SMALLINT + CHECK over 1..8 → 편→장→절→관→조→항→호→목) per ADR-006. `doc_type_code TEXT NULL` sibling column captures `법종구분코드` for provenance (ADR-007).
- No JSONB `metadata` column on either `legal_documents` or `structure_nodes` (ADR-008). Forward policy: promote when needed, omit deliberately, retain raw API XML as the canonical fallback. `chunks.metadata` JSONB is unaffected (separate role).
- Raw API XML retention committed via ADR-011: filesystem store at `data/raw/{law_id}/{mst}.xml`, indefinite retention, plain UTF-8, gitignored. Integrity link: SHA-256 of file = `legal_documents.content_hash`. Closes ADR-008's soft retention dependency.
- `parent_doc_id` self-FK on `legal_documents` for Act↔Decree linkage (ADR-009, amended by ADR-013). Asymmetric CHECK enforces "Acts have NULL parents"; a partial UNIQUE INDEX on `(title) WHERE doc_type='법률' AND is_head=true` backs the population-rule lookup; reverse-traversal index on `(parent_doc_id) WHERE parent_doc_id IS NOT NULL`. OSH 시행규칙 now makes Rule-parent assignment live verification work.
- `image_filenames TEXT[]` on `annexes` and `forms` (ADR-010 sub-decision; closes ADR-008 "Out of scope" #2).
- `structure_nodes.node_key` / `sort_key` population rules per ADR-012 (2026-05-03): tagless ASCII format `{조문키}-{HH}-{NN}{BB}-{KK}` with ordinal at 항/목, parsed `<호번호>`+`<호가지번호>` at 호. Branch numbering scope per _법령의개정방식과폐지방식_ — 조 and 호 only; verification trigger halts on any branch element at 편/장/절/관/항/목. **Phase-2 follow-up**: drop `sort_key` column (redundant with tagless `node_key`).

Open ERD TODOs (TODO-2, TODO-5, TODO-7) all ship as additive Phase-2 migrations; none blocks the freeze. Current phase is **canonical `eflaw` ingestion rollout**: ADR-020 accepted `target=eflaw` as canonical, `target=law` auxiliary only, `data/raw/eflaw/{law_id}/{mst}/{efYd}.xml` as the canonical raw path, and `(law_id, mst, effective_date)` as source-row identity. Migration `004`, canonical SAPA/OSH `eflaw` fetches, parser discovery/source-url support, and SAPA clean-DB ingest are verified. Parser normalizes ministry-prefixed Rule values such as `고용노동부령` to canonical DB `부령`; continue OSH parser/ingest gaps.

---

## 5. Working Agreements (Seheon's operating preferences)

- **Strong opinions, expressed.** Hedging is failure mode. State a position, then mark confidence.
- **Practical > novel.** Simpler shipped beats elegant unshipped.
- **Future-aware.** Decisions that will matter in 6 months outweigh current convenience.
- **Professional terminology.** No softening for accessibility.
- **Silence > fabrication.** If answering requires an unverified assumption — stop and surface it.
- **Partial answer > wrong answer.** Mark uncertainty explicitly: `<TBD>`, `<assumed>`, `<verify>`.
- **Devil's Advocation is a feature.** Seheon will challenge claims aggressively. Treat as design-strengthening, not adversarial.

---

## 5b. Decision Protocol — ADR-First, Then Approve

Any decision worth recording as an ADR (schema choice, identifier strategy,
table-split judgment, FK shape, etc.) follows this loop:

1. **Draft `docs/decisions/ADR-NNN-<slug>.md` first**, with status `Proposed`.
   State the recommendation, alternatives considered, and rationale — strong
   opinion expressed, not options-without-position.
2. **Surface the draft and ask Seheon for approval explicitly.** Do not edit
   the ERD, write DDL, or act on the decision yet.
3. **Only after approval**: flip status to `Accepted`, then act.

Decide-then-document inverts the review loop and presents Seheon a fait
accompli. The ADR is the editable surface for the conversation, not a
write-up after the fact. If you find yourself about to declare a decision
without a draft ADR in front of Seheon, stop and write the ADR first.

This rule applies to forward-applied decisions too — e.g., "future category
ERDs follow the same pattern" is itself a decision and needs its own ADR or
explicit approval.

---

## 6. Claude Slip Patterns — Internalize Before Substantive Response

Six recurring failure modes from prior sessions. These cost real time. Do not repeat.

1. **Inflation** — partial evidence → expansive inference → presented as confirmed.
   _Self-check_: "is this confirmed or inferred?" before assertion.
2. **Term invention** — e.g. "3-Layer Storage Pattern" stated as industry standard when it was Claude's own framing.
   _Self-check_: distinguish "named standard" vs "my framing" explicitly.
3. **Scope leak** — drifting into next-layer topics when Seheon explicitly scoped the current layer.
   _Self-check_: if straying, ask permission first.
4. **One-sided competitor evaluation** — stating a tool's weakness while ignoring an existing strength.
   _Self-check_: evaluate two-sided.
5. **Citing facts without source** — numbers / protocols / standards quoted from memory.
   _Self-check_: numbers and protocol facts require source or uncertainty mark.
6. **Detail misremembering** — e.g. QMD 2x weight assigned to wrong query (it's the **original**, not the expansion).
   _Self-check_: for specific mechanics, verify before stating.

---

## 7. Documentation Layout

```
legal-retrieval/
├── CLAUDE.md                   ← this file (entry point)
├── README.md                   ← public-facing
├── docs/
│   ├── phase-1-progress.md     ← full prior-session synthesis (553 lines)
│   ├── decisions/              ← ADR-NNN-<slug>.md (one per decision)
│   ├── sessions/               ← YYYY-MM-DD.md per work session
│   └── api-samples/            ← raw 법제처 API responses
├── src/
├── migrations/                 ← DDL versioned from day 1
├── scripts/                    ← fetchers, one-off utilities
└── tests/
```

**Read-on-demand pointers** (do not auto-load):

- Full prior context → `docs/phase-1-progress.md`
- Open decisions D-1 ~ D-7 → `docs/phase-1-progress.md` §6
- Phase 0 todo list T1 ~ T19 → `docs/phase-1-progress.md` §7

---

## 8. Session Protocol

**Start of session**

1. Skim this file.
2. Read latest `docs/sessions/*.md` — what did we end on?
3. Confirm current scope with Seheon before generating output.

**End of session**

1. Append to or create `docs/sessions/YYYY-MM-DD.md` — decisions made, open questions, next step.
2. If a decision was finalized → write `docs/decisions/ADR-NNN-<slug>.md`.
3. Commit. Decision narrative lives in git history. This is the portfolio artifact.

---

## 9. External Resources

- **법제처 OpenAPI**: `https://www.law.go.kr/DRF/`
  - `lawSearch.do` (search), `lawService.do` (fetch)
  - `target=law / prec / expc / admrul` for domain branching
  - XML primary, partial JSON support
- **공공데이터포털**: `data.go.kr`
- **KLRI (한국법제연구원)**: `klri.re.kr`
- **MCP precedent**: `chrisryugj/korean-law-mcp` — thin wrapper over 법제처 DRF API, no internal search index. This project occupies a different layer (search quality + multi-source integration + quantitative evaluation), not direct competition.

---

## 10. Out of Scope — Explicit

- Full RAG generation (G-layer).
- LangChain / LlamaIndex / any orchestrator framework.
- Non-statutory Phase-1 expansion before the SAPA + OSH statutory baseline is measured.
- LLM Router / Multi-agent before an evaluation baseline exists. _Anti-pattern: routing without measurement._

---

_Last updated: 2026-05-06 (after ADR-020 acceptance). Update on each ADR commit._
