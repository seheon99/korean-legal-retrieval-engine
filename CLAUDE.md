# Korean Legal Retrieval Engine — Project Operating Manual

This file is loaded automatically by Claude Code at the start of every session.
Keep it short. Treat it as a senior engineer's day-1 onboarding page.

---

## 1. Project Identity

Korean Legal Retrieval Engine — **R-layer only**, not full RAG.
Dual goal: production-grade retrieval engine + portfolio asset for H1 2027 hiring (Kakao / Naver / Coupang / Toss).
Owner: Seheon — freelance backend (Kotlin/Spring · TS/NestJS · Python); SeoulTech CS; SW Maestro 14기.

**Phase 1 Walking Skeleton**: 중대재해처벌법 (Serious Accidents Punishment Act, 2021).
Single statute end-to-end before any generalization. Scope is intentionally narrow.

---

## 2. Stack — Confirmed

| Layer            | Choice                              | Note                              |
|------------------|-------------------------------------|-----------------------------------|
| Runtime          | Python 3.11+ · FastAPI · pydantic   |                                   |
| Storage          | PostgreSQL + pgvector               | unified — **not** Qdrant          |
| Sparse retrieval | bm25s                               |                                   |
| Embeddings       | KURE or bge-m3                      | Korean-tuned; choice deferred     |
| Reranker         | bge-reranker-v2-m3                  |                                   |
| Forbidden        | LangChain · LlamaIndex              | direct implementation by design   |

---

## 3. Architecture — Confirmed

- **Retrieval pipeline reference**: QMD pattern.
  Original query + 2 expansions → BM25 / Vector parallel → RRF (**original query gets 2x weight, not the expansion**) → bge-reranker-v2-m3.
- **Load / Indexing separation** (RAGFlow framing).
  - Source ERDs per category — kept separate.
  - `chunks` table — unified search index, references source ERDs via FK.
  - One-line summary: *sources stay separated, search is unified, FKs connect them.*
- **Data categories** — 5, refined from initial 7:
  성문규범 · 사법판단 · 유권해석 · 학술자료 · 입법개정자료.
  부속참고 absorbed into 성문규범. 실무자료 handled separately.

---

## 4. Current Phase

Data Source Layer survey **complete**. Now starting **D-1: 성문규범 ERD**.

**Hard rule**: API response sample comes before schema design. We do not own the data — 법제처 does. Drawing the ERD before seeing the actual XML guarantees a rewrite.

Immediate next steps:
1. Fetch 중대재해처벌법 via 법제처 API → save to `docs/api-samples/`
2. Identify the natural entity tree from XML response
3. Layer our metadata (`effective_at`, `superseded_at`, `license`, `source_url`, `content_hash`)
4. Decide `chunks` FK granularity (article? paragraph?)

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

## 6. Claude Slip Patterns — Internalize Before Substantive Response

Six recurring failure modes from prior sessions. These cost real time. Do not repeat.

1. **Inflation** — partial evidence → expansive inference → presented as confirmed.
   *Self-check*: "is this confirmed or inferred?" before assertion.
2. **Term invention** — e.g. "3-Layer Storage Pattern" stated as industry standard when it was Claude's own framing.
   *Self-check*: distinguish "named standard" vs "my framing" explicitly.
3. **Scope leak** — drifting into next-layer topics when Seheon explicitly scoped the current layer.
   *Self-check*: if straying, ask permission first.
4. **One-sided competitor evaluation** — stating a tool's weakness while ignoring an existing strength.
   *Self-check*: evaluate two-sided.
5. **Citing facts without source** — numbers / protocols / standards quoted from memory.
   *Self-check*: numbers and protocol facts require source or uncertainty mark.
6. **Detail misremembering** — e.g. QMD 2x weight assigned to wrong query (it's the **original**, not the expansion).
   *Self-check*: for specific mechanics, verify before stating.

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
- Multi-domain coverage in Phase 1 (single statute first; expansion is Phase 2+).
- LLM Router / Multi-agent before an evaluation baseline exists. *Anti-pattern: routing without measurement.*

---

*Last updated: 2026-04-25. Update on each ADR commit.*
