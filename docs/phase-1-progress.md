# Korean Legal Retrieval Engine — Phase 1 Progress

> **Status**: Phase-1 statute ERD frozen (ADR-010, 2026-04-29). Schema committed at `migrations/001_statute_tables.sql`. ADR-009 population rule landed and DB-verified (2026-05-03). Idempotent re-ingest landed (2026-05-03). ADR-012 keying convention accepted (2026-05-03).
> **Generated**: Hand-off artifact for next session recall (now superseded by ADRs 001–012 for Phase-1 statute schema + ingestion decisions; this document remains canonical for cross-category context, license matrix, and DA log).
> **Next session task**: `_insert_children` parser depth (now unblocked by ADR-012). `structure_nodes` first per ADR-005.

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
- ✅ Domain: Korean law. Phase 1 narrowed to **Serious Accidents Punishment Act (중대재해처벌법)**.
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
- ✅ Serious Accidents Punishment Act (current)
- ✅ Enforcement Decree of the Act (current)
- 🔶 Selected Criminal Code articles referenced by the official commentary (DA #5)
- 🔶 Ministry of Employment notices on serious accidents (if applicable)
- ✅ Enforcement Decree appendices (sub-element of statutes)

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
- Occupational Safety and Health Act (high relevance but expands scope)
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
5. **Reranker**: bge-reranker-v2-m3 (Phase 3+)
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

- **Phase 1 (Walking Skeleton)**: single law + enforcement decree + commentary, BM25 only, no Query Rewriting
- **Phase 2**: add Query Rewriting, Vector + RRF
- **Phase 3**: add Reranker, formalize evaluation set
- **Phase 4**: add cross-reference graph, activate temporality

---

## 6. Open Decisions ❓

To be resolved in the next session:

✅ **D-1: RESOLVED** — Statute ERD scope = **Option B** (Act + Enforcement Decree + Enforcement Rules + appendices/forms). For 중대재해처벌법 specifically, this collapses to Option A (no 시행규칙 exists for this statute). Resolved by TODO-3 cleanup + ADRs 001/002. Schema frozen by ADR-010 (`migrations/001_statute_tables.sql`).

❓ **D-2**: License of public-agency manuals (KOSHA guides) — which KOGL type?

❓ **D-3**: License of MoE / MoLIT commentaries — which KOGL type?

❓ **D-4**: Whether law.go.kr OpenAPI actually exposes terminology-mapping endpoints, or whether the MCP server built that data separately — needs measurement

✅ **D-5: RESOLVED** — Document Parsing Pipeline (and other downstream layers) begin immediately after the Phase-1 statute DDL freeze (ADR-010). Walking-skeleton goal: 중대재해처벌법 end-to-end before generalizing. ERDs for other categories (judicial / interpretive / practical / academic) ship as parallel work, not as Phase-1 blockers.

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

⏸️ **T3-A**: Fetch the Serious Accidents Punishment Act body via curl/Python requests
- Confirm enforcement decree and rules are reachable too
- → `data/raw/중대재해처벌법/`

⏸️ **T4-A**: Analyze response structure
- Article/paragraph/item XML hierarchy
- Whether delegation references are exposed as metadata or only in body text
- Effective-date and amendment-history fields
- → `docs/data-sources/중대재해처벌법-schema.md`

⏸️ **T5-A**: Verify enforcement-decree and rules linkage metadata

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

⏸️ **T11-A**: Phase 1 raw-data dump

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

**Phase-1 statute ERD is frozen** as `migrations/001_statute_tables.sql` (ADR-010, 2026-04-29). Decision context for the Phase-1 statute schema + ingestion lives in `docs/decisions/ADR-001` through `ADR-012`. The current phase is **ingestion-pipeline implementation** (D-5 resolved; ADR-009 population rule landed and DB-verified 2026-05-03; idempotent re-ingest landed; ADR-012 keying convention accepted).

**Do immediately on next session**:

1. Read `CLAUDE.md` (entry point) and the latest `docs/sessions/*.md`.
2. Confirm scope with owner before generating output.
3. **`_insert_children` parser depth** is now top of the queue (unblocked by ADR-012). Walk the `<조문>` block, derive `node_key` per ADR-012 §1, set `parent_id` per the level hierarchy, populate the remaining `structure_nodes` columns from XML. Then `supplementary_provisions`, `annexes`, `forms` in order. `structure_nodes` is the highest-leverage piece per ADR-005 (primary chunk source).
4. **ADR-012 verification triggers** ship alongside `_insert_children`: (a) 조문키 shape `^[0-9]{7}$` + decoded `<조문번호>`/`<조문가지번호>`/`<조문여부>` agreement; (b) halt on any `<항가지번호>` / `<목가지번호>` / level-1..4 가지번호 element (per *법령의개정방식과폐지방식*: branches at 조 + 호 only).
5. **ADR-006 verification trigger** still pending — fires on first ingestion of any 시행규칙-bearing statute (must verify `<법종구분>` is exactly `'총리령'` or `'부령'`, not a ministry-prefixed variant).
6. **Amendment-tracking ADR (ADR-013 placeholder)** — decides what `_skip_if_present`'s mismatch branch should do for real amendments. Today: hard fail (`ContentMismatchError`). Future: auto-supersede pattern. Tied to TODO-5 + ADR-012 Trade-off §4 (sub-조 key fragility across amendments).
7. Open ERD TODOs (TODO-2, TODO-5, TODO-7) ship as additive Phase-2 migrations; none blocks ingestion-pipeline work.

**Closed dependencies** (no longer on the implement-list):
- ADR-008 raw-API-XML retention dependency — closed by ADR-011 on 2026-05-01.
- ADR-009 population rule — landed and DB-verified on 2026-05-03 (one Act + one Decree, parent FK populated correctly).
- Idempotent re-ingest — landed on 2026-05-03 with `_skip_if_present` + `ContentMismatchError`.

**Phase-2 follow-up parking lot** (separate ADRs at the boundary):
- Drop `sort_key` column per ADR-012 §Consequences — redundant with tagless `node_key` under the accepted encoding.
- Migration tool selection (sqitch / dbmate / Alembic) when `002_*.sql` ships.
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
  - Phase 1 indexes only the current version, but the schema should accommodate history
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
- v1.2 (2026-05-03): ADR-009 population rule landed and DB-verified end-to-end (one Act + one Decree ingested via `python -m ingest` against pgvector/pgvector:pg16 dev stack; parent FK resolved correctly via title-strip + UNIQUE INDEX). Idempotent re-ingest landed via `_skip_if_present` + `ContentMismatchError`. ADR-012 accepted: `structure_nodes` keying convention (tagless `{조문키}-{HH}-{NN}{BB}-{KK}`) + sort_key format + branch-numbering scope (조 + 호 only per *법령의개정방식과폐지방식*) + verification triggers. §10 Next Session Starting Guide rewritten around `_insert_children` parser depth, ADR-012 verification triggers, ADR-006 verification trigger (still pending), and amendment-tracking ADR-013 (placeholder). Phase-2 follow-up parking lot recorded (drop sort_key, migration tool, packaging). ADR range supersedes this document expanded from ADRs 001–010 to ADRs 001–012.
