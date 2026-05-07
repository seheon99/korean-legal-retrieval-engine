# Korean Legal Retrieval Engine — Project Operating Manual

This file is loaded automatically by Claude Code at the start of every
session. Keep it short. Treat it as a senior engineer's day-1 onboarding
page.

---

## 1. Project Identity

Korean Legal Retrieval Engine — **R-layer only**, not full RAG. The Phase-1
proof point is quantitative retrieval quality (Recall@K, MRR), not
ingestion polish.

Owner: Seheon — freelance backend (Kotlin/Spring · TS/NestJS · Python);
SeoulTech CS; SW Maestro 14기.

**Phase-1 statutory baseline** (ADR-019, 2026-05-06): SAPA + OSH full
families.

- `중대재해 처벌 등에 관한 법률`: Act + Enforcement Decree.
- `산업안전보건법`: Act + 시행령 + 시행규칙.

Retrieval/eval defaults to the legally effective slice as of 2026-05-06;
head/future rows require explicit query mode (ADR-013, ADR-021).

---

## 2. Stack — Confirmed

| Layer            | Choice                            | Note                            |
| ---------------- | --------------------------------- | ------------------------------- |
| Runtime          | Python 3.11+ · FastAPI · pydantic |                                 |
| Storage          | PostgreSQL + pgvector             | unified — **not** Qdrant        |
| Sparse retrieval | bm25s                             |                                 |
| Embeddings       | KURE or bge-m3                    | bake-off pending                |
| Reranker         | bge-reranker-v2-m3                |                                 |
| Forbidden        | LangChain · LlamaIndex            | direct implementation by design |

---

## 3. Architecture — Confirmed

- **Retrieval pipeline reference**: QMD pattern.
  Original query + 2 expansions → BM25 / Vector parallel → RRF
  (**original query gets 2x weight, not the expansion**) →
  bge-reranker-v2-m3.
- **Load / Indexing separation** (RAGFlow framing).
  Source ERDs per category stay separate; `chunks` is the unified search
  index referencing source ERDs via FK. _Sources stay separated, search is
  unified, FKs connect them._
- **Data categories**: 5 — see [docs/legal-data-categories.md](docs/legal-data-categories.md)
  for the canonical taxonomy and Phase-1 source inventory.
- **Retrieval contract**: legal-intent-first (ADR-021). Two operations —
  deterministic citation/identifier resolution and hybrid evidence
  retrieval. Engine owns operation routing; agents express legal intent,
  not retrieval knobs.

---

## 4. Current Phase

**Source ingestion: complete.** Default Compose DB rebuilt from canonical
`data/raw/eflaw` on 2026-05-06: 11 documents · 11,384 structure_nodes · 141
supplementary_provisions · 129 annexes · 774 annex_attachments · 222
forms · 712 form_attachments. Idempotent re-run skipped all 11 source rows
by hash.

**Live boundary: retrieval baseline.** See
[docs/phase-1-roadmap.md](docs/phase-1-roadmap.md) for the implementation
plan; first executable step is `migrations/005_chunks.sql`. Status, next
caveats, and open decisions live in
[docs/phase-1-progress.md](docs/phase-1-progress.md).

**Schema state (per ADRs 001–020).** Phase-1 statute ERD is frozen by
ADR-010 (`migrations/001_statute_tables.sql`). Migrations through
`004_eflaw_identity.sql` are applied. Five source tables:
`legal_documents`, `structure_nodes`, `supplementary_provisions`,
`annexes`, `forms`. Phase-1 chunk source FKs are closed at two:
`structure_node_id`, `annex_id` (ADR-003, ADR-005);
`supplementary_provisions` and `forms` are persistence-only. Canonical raw
XML lives at `data/raw/eflaw/{law_id}/{mst}/{efYd}.xml` (ADR-011 / ADR-020;
SHA-256 = `legal_documents.content_hash`). `node_key` / `sort_key`
population follows ADR-012 (tagless ASCII;
branch numbering at 조 and 호 only).

**Open prerequisites.** Rule `parent_doc_id` (ADR-009 follow-up) is the
first 시행규칙 revisit trigger. Binary attachment retention metadata
(`stored_file_path`, `checksum_sha256`, `fetched_at`) is reset by the DB
rebuild and needs a downloader rerun if durable paths/checksums are
required. ADR-018 production tokenizer is undecided. ADR-022 (graph
modeling roadmap) is `Proposed` — no graph schema or projection work until
it accepts.

---

## 5. Working Agreements

- **Strong opinions, expressed.** Hedging is failure mode. State a
  position, then mark confidence.
- **Practical > novel.** Simpler shipped beats elegant unshipped.
- **Future-aware.** Decisions that will matter in 6 months outweigh
  current convenience.
- **Professional terminology.** No softening for accessibility.
- **Silence > fabrication.** If answering requires an unverified
  assumption, stop and surface it.
- **Partial answer > wrong answer.** Mark uncertainty explicitly: `<TBD>`,
  `<assumed>`, `<verify>`.
- **Devil's Advocation is a feature.** Seheon will challenge claims
  aggressively. Treat as design-strengthening, not adversarial.

---

## 5b. Decision Protocol — ADR-First, Then Approve

Any decision worth recording as an ADR (schema choice, identifier
strategy, table-split judgment, FK shape, retrieval contract, etc.)
follows this loop:

1. **Draft `docs/decisions/ADR-NNN-<slug>.md` first**, with status
   `Proposed`. State the recommendation, alternatives considered, and
   rationale — strong opinion expressed, not options-without-position.
2. **Surface the draft and ask Seheon for approval explicitly.** Do not
   edit the ERD, write DDL, or act on the decision yet.
3. **Only after approval**: flip status to `Accepted`, then act.

Decide-then-document inverts the review loop. If you find yourself about
to declare a decision without a draft ADR in front of Seheon, stop and
write the ADR first.

This rule applies to forward-applied decisions too — e.g., "future
category ERDs follow the same pattern" is itself a decision and needs its
own ADR or explicit approval.

---

## 6. Claude Slip Patterns — Internalize Before Substantive Response

Six recurring failure modes from prior sessions. Re-anchoring on these is
free; reproducing them costs real time.

1. **Inflation** — partial evidence → expansive inference → presented as
   confirmed. _Self-check_: "is this confirmed or inferred?" before
   assertion.
2. **Term invention** — e.g. "3-Layer Storage Pattern" stated as industry
   standard when it was Claude's own framing. _Self-check_: distinguish
   "named standard" vs "my framing" explicitly.
3. **Scope leak** — drifting into next-layer topics when Seheon explicitly
   scoped the current layer. _Self-check_: if straying, ask permission
   first.
4. **One-sided competitor evaluation** — stating a tool's weakness while
   ignoring an existing strength. _Self-check_: evaluate two-sided.
5. **Citing facts without source** — numbers / protocols / standards
   quoted from memory. _Self-check_: numbers and protocol facts require
   source or uncertainty mark.
6. **Detail misremembering** — e.g. QMD 2x weight assigned to the wrong
   query (it's the **original**, not the expansion). _Self-check_: for
   specific mechanics, verify before stating.

Common shape: evidence arrives → meaning inflated → presented as confirmed
→ Seheon catches → correction. Pre-empt by asking "confirmed or inferred?"
before any assertion.

---

## 7. Documentation Layout

```
korean-legal-retrieval-engine/
├── AGENTS.md                       ← this file (entry point)
├── README.md                       ← public-facing
├── docs/
│   ├── phase-1-progress.md         ← state + next-session hand-off
│   ├── phase-1-roadmap.md          ← retrieval-baseline implementation plan
│   ├── legal-data-categories.md    ← 5-category taxonomy + Phase-1 sources
│   ├── design-principles.md        ← 13 durable design principles
│   ├── legal-erd.md                ← ERD reference (superseded for statute scope by ADRs 001–020)
│   ├── decisions/                  ← ADR-NNN-<slug>.md (one per decision)
│   └── sessions/                   ← YYYY-MM-DD.md per work session
├── data/
│   └── api-samples/                ← local-only raw 법제처 API responses
├── src/
├── migrations/                     ← raw SQL versioned from day 1
├── scripts/                        ← fetchers, one-off utilities
└── tests/
```

**Read-on-demand pointers** (do not auto-load):

- State + next-session task → [docs/phase-1-progress.md](docs/phase-1-progress.md)
- Live implementation plan → [docs/phase-1-roadmap.md](docs/phase-1-roadmap.md)
- Open decisions and outstanding inventory tasks → sections in
  `docs/phase-1-progress.md`.
- Per-decision rationale → `docs/decisions/ADR-*.md`.
- Per-session narrative → `docs/sessions/YYYY-MM-DD.md`.

---

## 8. Session Protocol

**Start of session**

1. Skim this file.
2. Read latest `docs/sessions/*.md` — what did we end on?
3. Confirm current scope with Seheon before generating output.

**End of session**

1. Append to or create `docs/sessions/YYYY-MM-DD.md` — decisions made,
   open questions, next step.
2. If a decision was finalized → write `docs/decisions/ADR-NNN-<slug>.md`.
3. Commit. Decision narrative lives in git history. This is the portfolio
   artifact.

---

## 9. External Resources

- **법제처 OpenAPI**: `https://www.law.go.kr/DRF/`
  - `lawSearch.do` (search), `lawService.do` (fetch).
  - `target=law / eflaw / prec / expc / admrul` for domain branching.
  - `target=eflaw` is the canonical statute XML source per ADR-020.
  - XML primary, partial JSON support.
- **공공데이터포털**: `data.go.kr`
- **KLRI (한국법제연구원)**: `klri.re.kr`
- **MCP precedent**: `chrisryugj/korean-law-mcp` — thin wrapper over 법제처
  DRF API, no internal search index. KLRE occupies a different layer
  (search quality + multi-source integration + quantitative evaluation),
  not direct competition.

---

## 10. Out of Scope — Explicit

- Full RAG generation (G-layer).
- LangChain / LlamaIndex / any orchestrator framework.
- Non-statutory Phase-1 expansion before the SAPA + OSH statutory baseline
  is measured.
- LLM Router / multi-agent before an evaluation baseline exists.
  _Anti-pattern: routing without measurement._
- Physical graph storage, projection jobs, or graph DB selection — Phase-1
  graph work is a contract over the current ERD only (ADR-022, proposed).

---

_Last updated: 2026-05-07 (post-ingest, retrieval baseline boundary;
ADR-021 accepted, ADR-022 proposed). Update on each ADR commit._
