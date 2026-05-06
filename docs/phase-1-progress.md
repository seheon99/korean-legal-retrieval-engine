# Korean Legal Retrieval Engine — Phase 1 Progress

> **Status**: Phase-1 statute ERD frozen (ADR-010, 2026-04-29), amended by ADR-013 (`is_current` → `is_head`) and ADR-014 (parallel `annex_attachments` / `form_attachments`; no `attachment_blobs` in Phase 1). ADR-015 accepted raw SQL migration management with a `schema_migrations` ledger. ADR-016 accepted annex attachment binary retention under `data/annexes/`; ADR-017 narrows default retention to PDF with HWP fallback; ADR-018 de-layouts annex `content_text` for retrieval. ADR-019 expands Phase 1 from SAPA-only to the SAPA + OSH full statutory families and makes the first retrieval baseline hybrid. ADR-020 accepted `target=eflaw` as the canonical statute XML source. Canonical SAPA/OSH `eflaw` ingest now parses and loads all source tables: `legal_documents`, `structure_nodes`, `supplementary_provisions`, `annexes`, `annex_attachments`, `forms`, and `form_attachments`. Clean throwaway DB verification: 11 documents, 11,384 structure nodes, 141 supplementary provisions, 129 annexes, 774 annex attachments, 222 forms, 712 form attachments. Default Compose DB still needs an explicit replacement posture because older rows were loaded from legacy `target=law` XML.
> **Generated**: Hand-off artifact for next session recall (now superseded by ADRs 001–020 for accepted Phase-1 statute schema, ingestion, scope, and raw-identity decisions).
> **Next session task**: choose the default DB replacement posture, then either rebuild the dev DB from canonical `eflaw` or define an explicit legacy-row replacement step.

---

## Confidence Markers

- ✅ **Confirmed**: Verified by measurement or documentation
- 🔶 **Agreed**: Decided by agreement before measurement
- ⚠️ **Hypothesis**: Unverified assumption (needs verification next session)
- ❓ **Open**: Decision required

---

## 1. Project Identity

**One-line definition** 🔶
> A **Retrieval Engine prototype** that integrates Korean statutory data with materials outside the law.go.kr API (commentaries, public agency manuals, academic papers), enriches metadata, and exposes a unified search interface. Quantitatively validates a hybrid search + Query Rewriting + Reranker pipeline (Recall@K, MRR) on Korean legal data.

**Scope decisions** 🔶
- ✅ Retrieval-only (R-layer of RAG). Generation is out of scope.
- ✅ Domain: Korean law. Phase 1 scope is now the **SAPA + OSH statutory neighborhood**: `중대재해 처벌 등에 관한 법률` family plus `산업안전보건법` family (ADR-019).
- ✅ Goal: engine maturity + portfolio for Korean big-tech recruiting (target: H1 2027).

**Owner background (for recall)**
- Freelance backend developer (Kotlin/Spring, TypeScript/NestJS, Python)
- SeoulTech CS, SW Maestro 14th cohort
- Concurrent projects: adoto, OpenClaw
- Current environment: law.go.kr OC key restricted by IP whitelist (cafe Wi-Fi blocks API calls)

---

## 2. Legal Data Categories (owner's final structure)

| Name | Description |
| ---- | ---- |
| 성문규범 (Statutes) | Normative texts enacted and promulgated by state authority with legal binding force |
| 사법판단 (Judicial Decisions) | Records of decisions by courts or the Constitutional Court on specific cases |
| 유권해석 (Authoritative Interpretation) | Official interpretations or quasi-judicial decisions by administrative agencies |
| 실무자료 (Practical References) | Reference materials issued by government and public agencies for practical work, without legal force |
| 학술자료 (Academic & Commentary) | Works by scholars or legal practitioners interpreting, systematizing, or critiquing law and case law |

**Evolution of categorization** ✅

This category set was reached through several Devil's Advocation rounds:
- Initial draft: 7 categories (statute / judicial / interpretive / academic / legislative / appendix / practical)
- DA #1 (taxonomic consistency): classification axes were mixed, creating boundary-case overhead → reduce
- DA #2 (raised by owner): appendices are part of the statute itself → tables and forms are absorbed into statutes
- Final: **5 categories** + metadata for fine-grained distinctions

**What was absorbed or merged** ✅
- Legislative materials → removed from top-level; deferred to Phase 2+
- Appendix/reference category → dissolved; appendices become a sub-element of statutes
- Administrative-appeal rulings → moved from judicial to **interpretive** (administrative procedure, not judicial)
- Ministry commentaries → debated between interpretive and practical → classified as **practical** (form and purpose, not authority)
- Supreme Court case commentaries → academic (content nature outweighs publisher)

---

## 3. Phase 1 Data Sources (owner's table)

| Type | Name | Source | Format |
| ---- | ---- | ---- | ---- |
| Statute | 성문규범 | law.go.kr API | XML |
| Judicial | 사법판단 | law.go.kr API | XML |
| Interpretive | 유권해석 | law.go.kr API | XML |
| Academic | KLRI publications | KLRI website | PDF |
| Practical | Ministry commentaries | Each ministry's website | PDF |
| Practical | Public agency manuals | Affiliated specialized agencies | PDF |
| Practical | Legal terminology | law.go.kr API | XML |

**Concrete Phase 1 scope** 🔶

Statute:
- ✅ Serious Accidents Punishment Act family: Act + Enforcement Decree
- ✅ Occupational Safety and Health Act family: Act + Enforcement Decree + Enforcement Rule (ADR-019; canonical `eflaw` files fetched)
- ✅ Effective-as-of `2026-05-06` is the default retrieval/eval slice; head/future rows are explicit-mode only
- 🔶 Selected Criminal Code articles referenced by the official commentary (DA #5)
- 🔶 Ministry of Employment notices on serious accidents (if applicable)
- ✅ Annexes are retained as statute sub-elements; forms are now live for OSH 시행규칙 but remain persistence-only

Judicial:
- 🔶 Only what the API returns (number to be measured)
- ⚠️ Estimated 20–30 cases (DA #2 requires actual measurement)

Interpretive:
- 🔶 Whatever the law.go.kr interpretation API returns
- ⏸️ Ministry of Employment Q&A as separate source: deferred to Phase 2

Practical:
- ✅ Ministry of Employment "Serious Accidents Punishment Act Commentary" (Nov 2021, KOGL Type 1)
- ✅ Ministry of Employment FAQ on the Act
- 🔶 KOSHA "Safety and Health Management System Guide" (license needs re-verification)

Academic:
- 🔶 KLRI materials (KOGL Type 4 — no-derivative restriction)
- 🔶 1–3 PDFs supplied manually by owner (converted to text first)

**Excluded (deferred to Phase 2+)**:
- Administrative regulations and rulings (Phase 3+)
- Legislative materials (proposal rationale, minutes, review reports — all deferred)
- Prosecution investigation guidelines (access uncertain)
- Ministry of Environment / Land commentaries (Phase 2)
- Law firm newsletters (copyright)
- Press articles on legal topics (copyright)

---

## 4. License Matrix

| Material | License | Body indexing | Metadata only | Commercial use |
| ---- | ---- | ---- | ---- | ---- |
| law.go.kr API data (statutes, cases, interpretations) | Public (assumed open) ⚠️ | ✅ | – | 🔶 |
| MoEL Serious Accidents Commentary | KOGL Type 1 ✅ | ✅ | – | ✅ |
| MoEL FAQ | Presumed KOGL Type 1 🔶 | ✅ | – | ✅ |
| KOSHA Safety Management Guide | Unknown ❓ | 🔶 | – | ❓ |
| KLRI research reports and journals | KOGL Type 4 ✅ | ⚠️ | ✅ | ❌ |
| MoE / MoLIT commentaries | Unknown ❓ | ❓ | ❓ | ❓ |
| KOSHA standard terminology CSV | Public data | ❌ (domain mismatch) | – | – |
| Academic papers (RISS, KCI) | Author copyright | ❌ | 🔶 (citation metadata only) | ❌ |
| Law firm newsletters | Firm copyright | ❌ | 🔶 (metadata only) | ❌ |
| Press articles | Press copyright | ❌ | ❌ | ❌ |

**Critical agreement — KOGL Type 4 in RAG context** 🔶

On the question "does a search engine's chunking and embedding count as data modification":
- ✅ Retrieval-only systems are compatible with Type 4 (gray area, but within citation scope)
- ❌ The Generation stage of RAG conflicts with Type 4 (LLM creates derivative work)
- 🔶 KLRI materials may be body-indexed in Phase 1; must be excluded if Generation is added in Phase 4+
- ✅ License managed as chunk metadata: `license_type`, `allowed_uses` fields

**KOSHA terminology CSV verification result** ✅
- 19,466 rows, but it is a database column dictionary for the agency's IT systems — no definitions or descriptions
- "Term + datatype" pairs, not "term + definition" pairs
- Unsuitable for Phase 1 retrieval
- Lesson: do not judge data.go.kr datasets by filename; sample inspection is required

---

## 5. Agreed Design Decisions

### Tech stack 🔶

1. **Language**: Python + FastAPI + Pydantic
2. **Database**: PostgreSQL + pgvector (fits Phase 1 scale, < 5M vectors)
3. **BM25**: bm25s library
4. **Embedding**: KURE or bge-m3 (Korean retrieval-tuned)
5. **Reranker**: bge-reranker-v2-m3 (Phase 1 hybrid baseline per ADR-019)
6. **Choice**: no LangChain or LlamaIndex — direct implementation (learning and portfolio value)

### Retrieval pipeline (Layer 5, Phase 2–4) 🔶

```
User query
    ↓
Query Rewriting (LLM produces original + N expansions)
    ↓
[original + expansions] each searched via BM25 + Vector
    ↓
RRF Fusion (original query weighted 2x — QMD pattern)
    ↓
Reranker (cross-encoder)
    ↓
Top-K
```

**Critical correction** ✅
- QMD's RRF gives **2x weight to the first/original query**, not to a specific subquery type (such as hyde)
- Owner caught this with the actual README diagram and CHANGELOG
- Citing CHANGELOG: "the user's actual words are a more reliable signal"

### Per-category source-structure design 🔶

This agreement is the foundation for the Phase 1 ERD work:

```
Statute ERD:
  legal_documents + structure_nodes (article/paragraph/item tree)

Judicial ERD:
  case_laws + case_sections (case number, holdings, reasoning)

Interpretive ERD:
  interpretations + interpretation_sections (inquiry, response, reasoning)

Practical / Academic ERD:
  commentaries + commentary_sections (light metadata + chapter/section)
```

**Per-category ERDs are separate; the search index is unified** 🔶
- Each category has its own ERD that preserves its native structure (owner's intuition was correct)
- The search-side `chunks` table sits in a separate layer where all sources land in a uniform shape
- The two layers are connected by foreign keys
- "Originals stay separate; only the search layer is unified" — resolved earlier confusion

### 13 design principles 🔶

Principles agreed across earlier sessions:
1. Interface-First (use Protocol)
2. Pluggable Components
3. Everything Measurable (explain mode, score traces)
4. Temporal-Ready but Not Temporal-Active
5. Multi-Source by Design (source_type from day one)
6. Collection as First-Class
7. Filters Not Afterthoughts
8. Indexing ⊥ Retrieval
9. Idempotent Indexing
10. Explicit Over Implicit
11. **Query Understanding is First-Class** (moved up to Phase 2)
12. **Authority-Aware Retrieval** (authority_level + judgment_status)
13. **Measure First, Plan Second** (no assumptions before measurement)

### Chunk metadata schema (draft) 🔶

```
chunks (
  chunk_id,
  source_type,                  -- statute | judicial | interpretive | practical | academic
  source_doc_id,
  source_node_id,               -- foreign key into the category-specific ERD
  text,
  context_prefix,
  embedding VECTOR(1024),

  -- authority and time
  authority_level,
  published_at,
  effective_at,
  superseded_at,

  -- category-specific
  court_level,                  -- when judicial
  judgment_status,              -- when judicial (disputed / established / referred-to-CC)
  interpretation_type,          -- when interpretive

  -- license
  license_type,                 -- public | kogl_type1 | kogl_type4 | etc.
  allowed_uses,                 -- ['retrieval', 'generation_context', 'redistribution']

  -- provenance
  producer,                     -- Ministry of Employment, Supreme Court, KOSHA, etc.
  metadata JSONB
)
```

### Phase roadmap 🔶

- **Phase 1 (SAPA + OSH statutory baseline)**: SAPA + OSH full statutory families, effective-as-of default, BM25 + vector + RRF + reranker, compare `bge-m3` and KURE before freezing embeddings
- **Phase 2**: broaden source categories after the statutory baseline is measured
- **Phase 3**: add Query Rewriting once baseline retrieval and evaluation exist
- **Phase 4**: add cross-reference graph, activate temporality

---

## 6. Open Decisions ❓

To be resolved in the next session:

✅ **D-1: RESOLVED** — Statute ERD scope = **Option B** (Act + Enforcement Decree + Enforcement Rules + appendices/forms). For 중대재해처벌법 specifically, this collapses to Option A (no 시행규칙 exists for this statute). Resolved by TODO-3 cleanup + ADRs 001/002. Schema frozen by ADR-010 (`migrations/001_statute_tables.sql`).

❓ **D-2**: License of public-agency manuals (KOSHA guides) — which KOGL type?

❓ **D-3**: License of MoE / MoLIT commentaries — which KOGL type?

❓ **D-4**: Whether law.go.kr OpenAPI actually exposes terminology-mapping endpoints, or whether the MCP server built that data separately — needs measurement

✅ **D-5: RESOLVED** — Document Parsing Pipeline (and other downstream layers) begin immediately after the Phase-1 statute DDL freeze (ADR-010). ADR-019 replaces the old single-statute walking skeleton with the SAPA + OSH full-family statutory baseline. ERDs for other categories (judicial / interpretive / practical / academic) ship as parallel work, not as Phase-1 blockers.

❓ **D-6**: Whether KLRI materials are included in Phase 1 body indexing (acceptance of the Type 4 gray area)

❓ **D-7**: Academic materials — who handles text conversion for owner-supplied PDFs? (Earlier agreement: owner converts before supplying)

---

## 7. Phase 0 To-Do List

Tasks agreed in earlier sessions (✅ done, 🔶 in progress, ⏸️ pending):

### To run as soon as IP restriction is lifted

⏸️ **T1**: law.go.kr OpenAPI registration and OC key issuance (owner already holds the key)

⏸️ **T2**: API endpoint catalog
- 17 domains via `target=law/prec/expc/admrul/ordin` etc.
- Document each response format and parameter set
- → `docs/data-sources/law-go-kr-api-catalog.md`

✅ **T3-A**: Fetch the Serious Accidents Punishment Act body via script
- Landed as `scripts/fetch_law_samples.sh` on 2026-05-01.
- Legacy raw XML was initially retained under `data/raw/{law_id}/{mst}.xml`
  per ADR-011; ADR-020 supersedes the canonical path to
  `data/raw/eflaw/{law_id}/{mst}/{efYd}.xml`.
- Confirmed Phase-1 statute corpus is Act `228817` + Decree `277417`; no 시행규칙 exists for this statute.

✅ **T4-A**: Analyze response structure
- Article/paragraph/item XML hierarchy
- Whether delegation references are exposed as metadata or only in body text
- Effective-date and amendment-history fields
- Superseded by `docs/legal-erd-draft.md`, ADRs 001–012, and the 2026-05-04 `structure_nodes` parser/tests.

✅ **T5-A**: Verify enforcement-decree and rules linkage metadata
- ADR-009 found no explicit parent-pointer metadata in 법제처 XML.
- Decree parent linkage is populated by title-strip lookup (`{Act title} 시행령` → Act) and DB-verified.
- Rules linkage remains deferred until a 시행규칙-bearing statute enters scope.

⏸️ **T6-B**: Measure case-law API coverage (strengthened)
- Counts by court level (Supreme / High / District)
- Counts where full text is retrievable
- → `docs/data-sources/판례-접근성-실측.md`

⏸️ **T7-A (extended)**: Reference-material inventory
- MoEL public materials
- KOSHA archive
- MoE and MoLIT publications
- Record URL + license notice for each

⏸️ **T8**: Confirm whether administrative-regulation and interpretation APIs exist (record as Phase 2+ candidates)

⏸️ **T9**: Terms-of-use review
- law.go.kr API ToS
- Redistribution, commercial use, attribution obligations
- → `docs/data-sources/license-compliance.md`

⏸️ **T10-A**: Document Phase 1 data scope
- → `docs/phase-1-scope.md`

🔶 **T11-A**: Phase 1 raw-data dump
- Statute raw XML dump exists for the Act/Decree Phase-1 corpus under `data/raw/`.
- Broader Phase-1 non-statute sources still pending.

⏸️ **T15**: Inventory Criminal Code articles cited by the commentary
- Extract referenced articles from MoEL commentary
- Enumerate ~30–50 articles
- → `docs/data-sources/referenced-criminal-law-articles.md`

⏸️ **T16**: Build a license-typed material classification table

⏸️ **T17**: Decide metadata-collection strategy for copyright-strict materials

⏸️ **T18**: Measure law.go.kr terminology API
- Actually call `get_legal_term_kb`, `get_daily_to_legal`, `get_legal_to_daily`
- Confirm whether the data origin is the law.go.kr OpenAPI

⏸️ **T19**: Investigate KOSHA safety-and-health terminology resources (the standard-terminology CSV is already disqualified)

### Optional

⏸️ **T12**: Hands-on test of natural-language search on law.go.kr (record limitations)
⏸️ **T13**: Skim the LBox Open dataset format
⏸️ **T14**: Confirm access to legislative-proposal rationales via the National Assembly bill information system (Phase 2+)

---

## 8. Devil's Advocation Log

Self-verification rounds for this project. Each affected design decisions.

### DA #1 — Are 7 categories correct?

**Attack**: Classification axes were inconsistent, raising boundary-case cost.
**Result**: ✅ Reduced 7 to 5 (reflected in owner's final structure).

### DA #2 — Aren't appendices part of statutes?

**Attack** (raised by owner): Appendices are promulgated alongside the law and carry the same legal force.
**Result**: ✅ Dissolved the appendix category. Appendices become a sub-element of statutes.

### DA #3 — "Judicial decisions" as a single category is too heterogeneous

**Attack**: Authority levels of Supreme Court / High / District / Constitutional differ greatly.
**Result**: 🔶 Solved not by splitting categories but by metadata (court_level, judgment_status).

### DA #4 — Korea-specific design = limited extensibility

**Attack**: Hard to extend to other jurisdictions.
**Result**: ✅ Acknowledged but no current action. Explicitly position the project as Korea-specific.

### DA #5 — From a search standpoint, do 7 categories matter?

**Attack**: Fewer categories with richer metadata is more practical.
**Result**: ✅ Settled on 5 categories + rich metadata.

### DA #6 — The premise of forcing all materials into the taxonomy is risky

**Attack**: Boundary materials always exist; perfect classification is impossible.
**Result**: ✅ Abandoned the 100% coverage goal. Treat the taxonomy as evolving.

### DA #7 — 16 articles is too few for statistical resolution

**Attack**: An ablation study would not be possible.
**Result**: ✅ Phase 1's purpose is a Walking Skeleton; ablation study is for Phase 2+.

### DA #8 — The "35 cases" assumption is unverified

**Attack**: API accessibility was never measured.
**Result**: ✅ Strengthened T6-B as an explicit measurement task.

### DA #9 — The law itself is unstable (referral to Constitutional Court + unsettled case law)

**Attack**: Search results can become misinformation.
**Result**: ✅ Use a `judgment_status` metadata field to mark disputed / established / referred-to-CC.

### DA #10 — Commentary quality and timeliness vary

**Attack**: Commentaries lag behind case-law changes.
**Result**: ✅ Use `authority_level` and `published_at` metadata to expose authority and recency.

### DA #11 — The Criminal Code body is missing

**Attack**: The Serious Accidents Punishment Act is a Criminal Code special law; without Criminal Code text the practical value is halved.
**Result**: ✅ Selectively index only Criminal Code articles cited by the official commentary.

### DA #12 (raised by owner) — Self-contradiction on natural-language queries

**Attack**: The MCP has natural-language routing, so saying "weak at natural language" is a contradiction.
**Result**: ✅ Claude admitted the contradiction. The value of vector search was reframed as conditional, not absolute.

### DA #13 (raised by owner) — Is RRF actually necessary?

**Attack**: The premise that law.go.kr's existing search is weaker has not been demonstrated.
**Result**: ✅ Demoted to a hypothesis. Phase 1 must include comparative measurement (law.go.kr vs the new engine).

---

## 9. Claude's Slip Log (warning to the next session)

**To the Claude of the next session**: these are the recurring slip patterns observed in this project.
If the same pattern resurfaces, the owner should stop the conversation immediately.

### Slip #1: Inventing terminology

**What happened**: Used "3-Layer Storage Pattern" as if it were industry-standard terminology.
**Reality**: Not a standard term. RAGFlow's "Load vs Indexing" is the closest legitimate phrasing.
**How owner caught it**: Asked for verification.
**Guard rail**: When using new terminology, verify the source. No invented names.

### Slip #2: Over-reading document fragments

**What happened**: Asserted "QMD's first-query-2x means hyde gets 2x weight."
**Reality**: Both the README diagram and the CHANGELOG say "the original query gets 2x weight."
**How owner caught it**: Attached the actual README diagram.
**Guard rail**: When interpreting document fragments, do not synthesize speculative inferences. Verify against the source.

### Slip #3: Asserting bidirectional mapping

**What happened**: From the existence of an MCP terminology-mapping tool, jumped to "law.go.kr provides this officially."
**Reality**: Only the existence of the MCP tool is verified; the data origin (direct from law.go.kr API vs separately constructed) is unknown.
**How owner caught it**: Asked "is that really the case?"
**Guard rail**: Do not extrapolate from "the tool exists" to "the upstream API provides it."

### Slip #4: Layer trespass

**What happened**: While in the Data Source Layer, drifted into ERD, chunks table, and search-index design.
**How owner caught it**: "Hey! This is exactly what gets confusing! I told you to start from the Data Source Layer!"
**Guard rail**: Do not move outside the layer the owner has named. "Considering" another layer and "focusing on" another layer are different.

### Slip #5: Treating assumptions as facts

**What happened**: Used unverified numbers like "35 cases reachable" as if confirmed.
**How owner caught it**: DA #8 demanded measurement.
**Guard rail**: Do not state numbers without "estimated" or "expected" qualifiers when unverified.

### Slip #6: Underestimating competing products

**What happened**: Asserted "the MCP is weak on natural language."
**Reality**: The MCP handles natural language via LLM tool routing; it just lacks vector search.
**How owner caught it**: Pointed out the contradiction with my own earlier statement.
**Guard rail**: When evaluating competing products, weigh strengths and weaknesses simultaneously.

### Common pattern

The shared structure of these six slips:
1. A piece of evidence arrives.
2. **Inflate** its meaning by extrapolation.
3. Present it **as if confirmed**.
4. Owner asks for verification or points out a contradiction.
5. Claude corrects.

**Preventive behavior**:
- Before stating new information: ask "is this confirmed or inferred?"
- When citing numbers, standards, or official facts: state the source.
- When evaluating a competing product: cover both strengths and weaknesses.
- When stepping outside the explicit scope: ask permission first.

---

## 10. Next Session Starting Guide

**Phase-1 statute ERD is frozen** as `migrations/001_statute_tables.sql` (ADR-010, 2026-04-29), with ADR-013 amending the temporality flag from `is_current` to `is_head` and ADR-014 adding parallel `annex_attachments` / `form_attachments` while deferring `attachment_blobs`. ADR-015 sets post-freeze migration management as ordered raw SQL files plus a `schema_migrations` ledger. ADR-016 stores downloaded annex binaries under `data/annexes/`; ADR-017 makes PDF the default retained format with HWP fallback; ADR-018 defines annex content de-layout normalization. ADR-019 expands Phase 1 from SAPA-only to SAPA + OSH full statutory families and pulls the first hybrid retrieval baseline into Phase 1. Accepted decision context for the Phase-1 statute schema, ingestion, scope, and raw identity lives in `docs/decisions/ADR-001` through `ADR-020`. The current phase is **canonical `eflaw` ingestion rollout**. A clean throwaway DB verified canonical SAPA + OSH ingestion across all Phase-1 source tables. The default Compose DB has migration `004` but still needs explicit replacement/rebuild because it was previously loaded from legacy `target=law` XML.

**Do immediately on next session**:

1. Read `CLAUDE.md` (entry point) and the latest `docs/sessions/*.md`.
2. Confirm scope with owner before generating output.
3. **Recommended next action: choose DB replacement posture.** Canonical SAPA `eflaw` bytes differ from legacy `target=law` bytes, so existing rows should be clean-rebuilt or explicitly replaced, not silently updated by idempotent ingest.
4. After replacement, run canonical `eflaw` ingest against the default Compose DB and verify counts against the clean smoke result.
5. Rule `parent_doc_id` remains the ADR-009 revisit trigger: first 시행규칙-bearing statute is now in scope, but Act-vs-Decree parentage needs a follow-up ADR before implementation.
6. **Decide the ADR-018 production boundary scorer.** Current annex de-layouting uses a reviewed deterministic Phase-1 substitute; choose the Korean tokenizer / morphological analyzer before broadening the scorer.
7. **ADR-006 verification is closed for OSH Rule.** 법제처 confirms 시행령 = `대통령령` and 시행규칙 = `총리령ㆍ부령`; parser normalization maps ministry-prefixed `*부령` values such as `고용노동부령` to canonical DB `부령`.
8. **Heading generalization is open outside the SAPA + OSH corpus.** OSH inline branched `<호번호>` values such as `3의2.` are handled; the older broad-smoke issue for unrelated `형법` multiple-`전문` headings remains outside Phase 1.
9. Open ERD TODOs (TODO-2, TODO-5, TODO-7) ship as additive Phase-2 migrations; none blocks ADR-019 OSH discovery.

**Closed dependencies** (no longer on the implement-list):
- ADR-008 raw-API-XML retention dependency — closed by ADR-011 on 2026-05-01.
- ADR-009 population rule — landed and DB-verified on 2026-05-03 (one Act + one Decree, parent FK populated correctly).
- Idempotent re-ingest — landed on 2026-05-03 with `_skip_if_present` + `ContentMismatchError`.
- `structure_nodes` parser depth — landed on 2026-05-04. Parses the `<조문>` block, materializes implicit 항 rows, derives ADR-012 `node_key` / `sort_key`, inserts parent-linked rows, normalizes `number` (`4.` → `4`, `가.` → `가`), and implements ADR-012 verification triggers.
- ADR-015 migration management — accepted on 2026-05-05. Post-freeze migrations are ordered raw PostgreSQL SQL files with a `schema_migrations` ledger.
- ADR-014 annex ingestion — landed on 2026-05-05. `002_annex_form_attachments.sql` adds `annex_attachments` and `form_attachments`; parser validates the `<별표단위>` discriminator/key contract; populate inserts 5 Decree annexes and 21 source attachment-reference rows.
- ADR-016 annex binary retention — accepted and landed on 2026-05-05. `scripts/download_annex_attachments.py` downloads HWP/PDF/image files to `data/annexes/{law_id}/{mst}/{annex_key}/{filename}`, uses OC only as request credential, stores repo-relative paths/checksums/fetch timestamps, and discovers image URLs through verified rendered law.go.kr annex content with strict rendered-order matching.
- ADR-013 rename migration — landed on 2026-05-06. `003_is_head_rename.sql` renames temporal source-table flags from `is_current` to `is_head`; populate now uses `is_head` for Act parent lookup and child inserts.
- Running dev DB fill — current counts after 2026-05-06 rename verification: 2 `legal_documents`, 240 `structure_nodes`, 232 non-root `structure_nodes` with `parent_id`, 5 `annexes`, 21 `annex_attachments`; 5 PDF rows stored/checksummed/fetched, HWP/image rows provenance-only.
- ADR-019 Phase-1 OSH scope expansion — accepted on 2026-05-06. Phase 1 now targets SAPA + OSH full statutory families, with current-law retrieval/eval defaulting to the legally effective slice as of 2026-05-06 and hybrid retrieval as the first baseline.
- ADR-020 `eflaw` canonical statute XML source — accepted on 2026-05-06 after OSH discovery proved same-MST/different-efYd XML divergence; `target=law` is auxiliary only.
- ADR-020 executable slice — landed on 2026-05-06. `004_eflaw_identity.sql`, canonical SAPA `eflaw` fetches, parser discovery/source-url support, and `(law_id, mst, effective_date)` idempotency are clean-DB verified.
- OSH canonical `eflaw` fetch — completed on 2026-05-06. Act and Decree parse at doc level; Rule `고용노동부령` now normalizes to canonical DB `부령`.
- OSH source-table ingestion — completed in the 2026-05-06 night session. Parser handles OSH inline branched `<호번호>` values, inserts persistence-only `supplementary_provisions`, inserts metadata-only `forms` plus `form_attachments`, and applies ADR-013 supersession to `legal_documents`, `structure_nodes`, `annexes`, and `forms`.

**Phase-2 follow-up parking lot** (separate ADRs at the boundary):
- Drop `sort_key` column per ADR-012 §Consequences — redundant with tagless `node_key` under the accepted encoding.
- Migration runner script around ADR-015's raw SQL + `schema_migrations` convention.
- Packaging (`pyproject.toml`) when host-side Python work is needed beyond Docker.

**When designing the ERD, keep these other-layer considerations in mind** (earlier agreements):

- **Document Parsing Pipeline**:
  - Mapping from law.go.kr XML to ERD fields
  - Delegation references ("as prescribed by Presidential Decree")
  - Criminal Code references (DA #5)
  - Enforcement decree appendices (HWP/HWPX)

- **Indexing Layer**:
  - Stable `node_id` so chunks can reliably back-reference statutes
  - Whether `node_id` is preserved across amendments, or versioned

- **Retrieval Pipeline**:
  - The relational structure should make it natural to return the article + appendix + delegated decree article together

- **Temporality**:
  - Phase 1 indexes the head/effective version as required by query semantics, but the schema should accommodate history
  - Reserve `effective_at`, `superseded_at` fields up front

**What should naturally follow the ERD work**:
- Document Parsing Pipeline design
- ERDs for the other categories (judicial, interpretive, etc.)
- Integration of license metadata fields

---

## 11. Key References

### External resources

- **law.go.kr OpenAPI**: `https://www.law.go.kr/DRF/`
  - `lawSearch.do` (search), `lawService.do` (retrieval)
  - `target` parameter switches the domain
  - Default response is XML; some endpoints support JSON
- **data.go.kr (Public Data Portal)**: file-based data format
- **Ministry of Employment archive**: `moel.go.kr/policy/policydata`
- **Korea Legislation Research Institute (KLRI)**: `klri.re.kr`
- **MCP reference (community)**: `chrisryugj/korean-law-mcp`
  - 89 internal tools, 14 surfaced
  - Acts as a thin wrapper over the law.go.kr API
  - No internal search index of its own

### Technical references

- **QMD** (`tobi/qmd`): retrieval pipeline reference
  - Original query + 2 expansions → BM25/Vector in parallel → RRF (original 2x) → Reranker
- **Hybrid RAG** (2025 enterprise standard): Vector + Graph + Structured
- **RAGFlow**: Load vs Indexing framing
- **maastrichtlawtech/fusion**: hybrid retrieval reference for French law
- **LBox Open**: Korean case-law dataset (CC BY-NC, 147k cases)
- **KURE / bge-m3**: Korean retrieval embeddings

---

## 12. Change Log

- v1.0: initial artifact (compressed agreements)
- v1.1 (2026-04-29): Phase-1 statute ERD frozen via ADR-010 (`migrations/001_statute_tables.sql`). D-1 (statute ERD scope) and D-5 (parsing-pipeline timing) marked RESOLVED. §10 Next Session Starting Guide updated to reflect ingestion-pipeline phase. ADRs 001–010 supersede this document for Phase-1 statute schema decisions; remaining sections stay canonical for cross-category context, license matrix, and DA log.
- v1.2 (2026-05-03): ADR-009 population rule landed and DB-verified end-to-end (one Act + one Decree ingested via `python -m ingest` against pgvector/pgvector:pg16 dev stack; parent FK resolved correctly via title-strip + UNIQUE INDEX). Idempotent re-ingest landed via `_skip_if_present` + `ContentMismatchError`. ADR-012 accepted: `structure_nodes` keying convention (tagless `{조문키}-{HH}-{NN}{BB}-{KK}`) + sort_key format + branch-numbering scope (조 + 호 only per *법령의개정방식과폐지방식*) + verification triggers. §10 Next Session Starting Guide rewritten around `_insert_children` parser depth, ADR-012 verification triggers, ADR-006 verification trigger (still pending), and the amendment-tracking decision later drafted as ADR-013. Phase-2 follow-up parking lot recorded (drop sort_key, migration tool, packaging). ADR range supersedes this document expanded from ADRs 001–010 to ADRs 001–012.
- v1.3 (2026-05-04): `structure_nodes` parser depth landed and filled the running Compose `database` service: 2 `legal_documents`, 240 `structure_nodes`, 232 parent-linked child rows. ADR-012 verification triggers implemented in `src/ingest/parse.py`; parser now materializes implicit 항 rows and normalizes `structure_nodes.number` (`4.` → `4`, `가.` → `가`, future branched 호 as `7의2`). §7 statute-fetch/analyze tasks refreshed to reflect the landed fetch script, raw XML retention, and DB-verified ADR-009 linkage. §10 Next Session Starting Guide updated: `structure_nodes` is closed; recommended next action is `annexes` ingestion, followed by `supplementary_provisions`, with heading generalization for broad statutes recorded as an open parser issue.
- v1.4 (2026-05-04): ADR numbering corrected after review. ADR-013 is now the accepted amendment-tracking decision: immutable version rows, `is_current` replaced by `is_head`, same-MST mismatch remains hard fail, and legal effectiveness is computed from temporal predicates. Annex ingestion moved to ADR-014 and accepted with parallel `annex_attachments` / `form_attachments`, separating upstream `source_attachment_url` provenance from application-owned `stored_file_path`, rejecting polymorphic/shared-owner attachment tables per ADR-003, and deferring `attachment_blobs`; §10 now points to implementing ADR-014 annex ingestion first.
- v1.5 (2026-05-05): ADR-015 accepted migration management: ordered raw PostgreSQL SQL files plus `schema_migrations` ledger. `migrations/002_annex_form_attachments.sql` landed and was applied to the running Compose `database`; ADR-014 parser/populator implementation landed for `annexes` and `annex_attachments`. Phase-1 Decree sample now yields 5 annex rows and 21 attachment-reference rows, with HWP/PDF source URLs preserved verbatim, image filenames preserved in order, and binary storage fields left NULL. §10 now points to the ADR-013 rename migration, then persistence-only `supplementary_provisions` ingestion.
- v1.6 (2026-05-05): ADR-016 accepted annex attachment binary retention. Added `scripts/download_annex_attachments.py` and `data/annexes/` gitignore rule; downloaded 5 HWP + 5 PDF files for the Phase-1 Decree under `data/annexes/014159/277417/{annex_key}/`, updated `annex_attachments.stored_file_path`, `checksum_sha256`, and `fetched_at`, and verified DB checksums against local files. PDF review: page counts 2/2/4/2/1 match the 11 image filename rows; `pdftotext` extracts annex headings; `pdfimages` reports no embedded raster image objects. Image rows remain pending verified URL discovery or ADR-016 re-evaluation.
- v1.7 (2026-05-05): ADR-016 amended to permit strict rendered-order image URL matching when law.go.kr rendered annex content exposes image `flDownload.do` URLs without source filenames. Downloader discovered image URLs through `lawService.do` HTML redirect + `lsBylInfoR.do` + `lsBylContentsInfoR.do`, matched rendered URL counts against XML image row counts per annex, downloaded all 11 GIF files, stored clean non-OC `source_attachment_url` values, and verified local SHA-256 values against DB checksums. All 21 annex attachment rows are now locally retained.
- v1.8 (2026-05-05): ADR-017 accepted PDF-default retention with HWP fallback. Downloader default now selects PDF first and falls back to HWP only when PDF retention is unavailable or invalid; explicit `--types` still supports exact operator-selected retention. Local dev cleanup preserved all attachment provenance rows and retained only 5 PDF binaries.
- v1.9 (2026-05-05): ADR-018 accepted annex content de-layout normalization. `annexes.content_text` is parser-owned semantic text for retrieval while raw XML/PDF remain fidelity sources. Phase-1 annex hard-wrap repairs landed with parser tests and a refresh script for existing DB rows.
- v1.10 (2026-05-06): ADR-013 executable rename landed through `migrations/003_is_head_rename.sql`. `legal_documents`, `structure_nodes`, `annexes`, and `forms` now expose `is_head`; the head Act title index was renamed; populate uses `is_head` for Act parent lookup and source-row inserts. §10 now points to persistence-only `supplementary_provisions` ingestion or ADR-018 tokenizer selection.
- v1.11 (2026-05-06): ADR-019 accepted Phase-1 scope expansion from SAPA-only to SAPA + OSH full statutory families. §1, §3, §5, §6, and §10 now reflect OSH API discovery as the next step, effective-as-of `2026-05-06` as the default retrieval/eval slice, persistence-only `supplementary_provisions` / `forms`, and hybrid retrieval as the first baseline.
- v1.12 (2026-05-06): OSH API discovery started and hit ADR-019's explicit stop condition: `target=eflaw` produces distinct XML for the same `(law_id, mst)` at different `efYd` values. ADR-020 drafted with status `Proposed`; §10 now blocks OSH raw writes, migrations, parser changes, and ingestion rows until ADR-020 is accepted.
- v1.13 (2026-05-06): ADR-020 revised per Seheon's direction: `target=eflaw` is the proposed canonical statute XML source, `target=law` is auxiliary only, canonical raw path is `data/raw/eflaw/{law_id}/{mst}/{efYd}.xml`, and existing `data/raw/{law_id}/{mst}.xml` files are legacy data to replace or remove.
- v1.14 (2026-05-06): ADR-020 accepted. §10 now points to implementation: migration from `UNIQUE(mst)` to `(law_id, mst, effective_date)`, canonical `eflaw` fetches under `data/raw/eflaw/{law_id}/{mst}/{efYd}.xml`, and verified replacement/removal of legacy SAPA `target=law` raw XML.
- v1.15 (2026-05-06): ADR-020 executable slice landed. Added `004_eflaw_identity.sql`; upgraded fetch, parser discovery/source URL, and idempotency to canonical `eflaw`; fetched SAPA canonical `eflaw` XML; clean throwaway DB verified migrations `001`-`004` plus ingest. Existing running DB rows remain legacy-source rows and need clean rebuild or explicit replacement.
- v1.16 (2026-05-06): OSH canonical `eflaw` XML fetched for Act, Decree, and Rule current/future slices. Doc-level parsing initially succeeded for OSH Act/Decree and halted on OSH Rule `고용노동부령`, surfacing the ministry-prefixed rule handling gap later corrected in v1.17.
- v1.17 (2026-05-06 night): Corrected ADR-006 interpretation using 법제처 explanation: 시행령 is 대통령령 and 시행규칙 is 총리령/부령. Implemented parser normalization from ministry-prefixed `*부령` values such as `고용노동부령` to canonical DB `부령`; original value remains in retained raw XML and `doc_type_code` remains captured.
- v1.18 (2026-05-06 night): Canonical SAPA + OSH source ingestion verified end-to-end in clean throwaway DB `osh_ingest_smoke_20260506_night`: 11 `legal_documents`, 11,384 `structure_nodes`, 141 `supplementary_provisions`, 129 `annexes`, 774 `annex_attachments`, 222 `forms`, and 712 `form_attachments`. Implemented ADR-013 supersession lifecycle with KST `effective_at`, chronological phase ordering, temporal child supersession, supplementary provision inserts, form/form-attachment inserts, and inline branched 호번호 parsing (`3의2.` -> node key segment `0302`).
