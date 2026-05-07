# Statute (성문규범) ERD

> **Status**: Frozen — see `migrations/001_statute_tables.sql` per ADR-010 (Accepted 2026-04-29). Future schema changes ship as additive migrations (`002_*.sql`, ...).
> **Amendments**: ADR-013 replaces `is_current` with `is_head`. ADR-014 adds parallel `annex_attachments` / `form_attachments` tables, moves binary references out of `annexes` / `forms`, and defers `attachment_blobs`.
> **Scope**: Option B (Act + Enforcement Decree + Enforcement Rules + appendices/forms)
> **Basis**: earlier-session sketch (richer version) + law.go.kr XML analysis
> **Phase 1 domain**: 중대재해처벌법 (Serious Accidents Punishment Act)

---

## Confidence Markers

- ✅ Confirmed: agreed in earlier sessions or verified by XML
- 🔶 Agreed: decided by agreement before measurement
- ⚠️ Hypothesis: assumption, needs verification
- ❓ Open: requires a human decision

---

## ERD

```mermaid
erDiagram
    legal_documents ||--o{ structure_nodes : contains
    legal_documents ||--o{ supplementary_provisions : has
    legal_documents ||--o{ annexes : has
    legal_documents ||--o{ forms : has
    legal_documents ||--o{ legal_documents : parent_of
    structure_nodes ||--o{ structure_nodes : parent_of
    annexes ||--o{ annex_attachments : has
    forms ||--o{ form_attachments : has

    legal_documents {
        bigint doc_id PK "IDENTITY"
        bigint parent_doc_id FK "self-ref: 법률→NULL, 시행령→Act doc_id (per ADR-009)"
        text law_id "법령ID - shared across versions, NOT unique"
        bigint mst UK "법령일련번호 - version-specific natural key"
        text title "법령명_한글"
        text title_abbrev "법령명약칭 (nullable)"
        text law_number "공포번호 (e.g. 17907)"
        text doc_type "법률 | 대통령령 | 총리령 | 부령 (formal types per ADR-006)"
        text doc_type_code "법종구분코드 e.g. A0002 (machine-stable; nullable, per ADR-007)"
        text amendment_type "제정 | 일부개정 | 전부개정 | 타법개정"
        date enacted_date "공포일자"
        date effective_date "시행일자"
        text competent_authority "소관부처명"
        text competent_authority_code "소관부처코드"
        text structure_code "편장절관 8-digit code"
        text legislation_reason "제개정이유 (nullable)"
        text source_url "법령상세링크"
        text content_hash "SHA-256 of raw XML"
        timestamptz effective_at "Phase 2 temporality"
        timestamptz superseded_at "Phase 2 temporality"
        boolean is_head "Latest ingested version in law_id lineage (ADR-013)"
        timestamptz created_at
        timestamptz updated_at
    }

    structure_nodes {
        bigint node_id PK "IDENTITY"
        bigint doc_id FK "legal_documents.doc_id"
        bigint parent_id FK "structure_nodes.node_id (self-ref)"
        smallint level "1=편 2=장 3=절 4=관 5=조 6=항 7=호 8=목 (per ADR-006)"
        text node_key UK "조문키 - composite UK with doc_id"
        text number "e.g. 4 or 제4조의2"
        text title "조문제목 (nullable)"
        text content "본문 text"
        text sort_key "handles 제39조의2의2 ordering"
        date effective_date "조문시행일자"
        boolean is_changed "조문변경여부"
        text source_url "nullable"
        text content_hash "SHA-256 of content"
        timestamptz effective_at "Phase 2 temporality"
        timestamptz superseded_at "Phase 2 temporality"
        boolean is_head "Latest ingested version in doc lineage (ADR-013)"
        timestamptz created_at
        timestamptz updated_at
    }

    supplementary_provisions {
        bigint provision_id PK "IDENTITY"
        bigint doc_id FK "legal_documents.doc_id"
        text provision_key UK "부칙키 - composite UK with doc_id"
        date promulgated_date "부칙공포일자"
        int promulgation_number "부칙공포번호"
        text content "부칙내용 - free text"
        timestamptz created_at
        timestamptz updated_at
    }

    annexes {
        bigint annex_id PK "IDENTITY"
        bigint doc_id FK "legal_documents.doc_id"
        text annex_key UK "별표키 (E suffix) - composite UK with doc_id"
        text number "별표번호 (e.g. 0001)"
        text branch_number "별표가지번호 (e.g. 00 or for 별표 1의2)"
        text title "별표제목"
        text content_text "별표내용 inline text - SEARCH TARGET"
        text content_format "prose | table | mixed (parser-stage hint)"
        text source_url
        text content_hash "SHA-256 of content_text"
        timestamptz effective_at "Phase 2 temporality"
        timestamptz superseded_at "Phase 2 temporality"
        boolean is_head "Latest ingested version in doc lineage (ADR-013)"
        timestamptz created_at
        timestamptz updated_at
    }

    annex_attachments {
        bigint attachment_id PK "IDENTITY"
        bigint annex_id FK "annexes.annex_id"
        text attachment_type "hwp | pdf | image"
        text source_attachment_url "exact upstream API link; provenance only"
        text source_filename "original filename from API"
        text stored_file_path "application-controlled storage path"
        text checksum_sha256 "SHA-256 of stored binary"
        timestamptz fetched_at "download timestamp"
    }

    forms {
        bigint form_id PK "IDENTITY"
        bigint doc_id FK "legal_documents.doc_id"
        text form_key UK "별표키 (F suffix) - composite UK with doc_id"
        text number "별표번호"
        text branch_number "별표가지번호"
        text title "별표제목 - SEARCH TARGET (only metadata)"
        text source_url
        timestamptz effective_at "Phase 2 temporality"
        timestamptz superseded_at "Phase 2 temporality"
        boolean is_head "Latest ingested version in doc lineage (ADR-013)"
        timestamptz created_at
        timestamptz updated_at
    }

    form_attachments {
        bigint attachment_id PK "IDENTITY"
        bigint form_id FK "forms.form_id"
        text attachment_type "hwp | pdf | image"
        text source_attachment_url "exact upstream API link; provenance only"
        text source_filename "original filename from API"
        text stored_file_path "application-controlled storage path"
        text checksum_sha256 "SHA-256 of stored binary"
        timestamptz fetched_at "download timestamp"
    }
```

### Context-only: chunks table (not part of this ERD)

The `chunks` table lives in a separate search-index layer. It references statute data via:

```
chunks.source_type = 'statute'
chunks.source_node_id → structure_nodes.node_id  (article body)
                       OR annexes.annex_id        (annex body)
                       -- forms are NOT a chunk source
```

**Forms are intentionally excluded from the search index.** Form bodies arrive as ASCII box-drawing text in `<별표내용>` — usable for display but actively harmful as retrieval input. Forms are reachable through metadata search (title, document_id) only.

Retrieval semantics:

```text
annexes -> chunks -> BM25/vector
forms -> metadata only
annex_attachments / form_attachments -> provenance and storage only
```

Attachments are not retrieval documents. They may support display,
download, or future text extraction, but they are not indexed directly.

This ERD must provide **stable identifiers** for chunks to back-reference.
See TODO-5 for retention policy.

---

## Entity Descriptions

### legal_documents

Represents a single statute document as a versioned unit. One row per law-version.

| Field | Confidence | Source / Rationale |
|-------|-----------|-------------------|
| `doc_id` | ✅ Resolved (TODO-4) | `BIGINT GENERATED ALWAYS AS IDENTITY`. Surrogate key. Single-column FK target for `chunks.source_id` |
| `parent_doc_id` | ✅ Resolved (ADR-009, amended by ADR-013) | `BIGINT NULL REFERENCES legal_documents(doc_id) ON DELETE RESTRICT`. Self-FK pointing to the immediately delegating document. Acts → NULL (enforced by `chk_legal_documents_act_no_parent`); Decrees → Act doc_id (populated at ingestion via title-pattern matching). Reverse traversal indexed by `ix_legal_documents_parent`; population-rule lookup uniqueness should be backed by a head-row partial UNIQUE on `(title) WHERE doc_type='법률' AND is_head=true`. Rules parent assignment deferred per ADR-009 "Out of scope" #2 |
| `law_id` | ✅ XML | `<법령ID>013993</법령ID>`. Identifies the law across versions — **not** in any UNIQUE constraint because multiple rows can share it once Phase 2 temporality is on |
| `mst` | ✅ Resolved (TODO-4) | `<법령일련번호>228817</법령일련번호>`. Version-specific natural key. **`UNIQUE` constraint** — drives idempotent upsert on re-ingestion |
| `title` | ✅ Sketch + XML | `<법령명_한글>` |
| `title_abbrev` | ✅ XML | `<법령명약칭>`. Present for this law ("중대재해처벌법"), nullable for others |
| `law_number` | ✅ Sketch + XML | `<공포번호>17907</공포번호>`. Official gazette number |
| `doc_type` | ✅ Resolved (ADR-006) | `TEXT` with `CHECK (doc_type IN ('법률', '대통령령', '총리령', '부령'))`. Stores the formal Korean type from `<법종구분>` element text — *not* the informal role names (시행령/시행규칙). Human-facing canonical |
| `doc_type_code` | ✅ Resolved (ADR-007) | `TEXT NULL`, no CHECK. Captured at ingestion from the `법종구분코드` attribute on `<법종구분>` (e.g., `A0002` for 법률, `A0007` for 대통령령). Machine-facing stable identifier; companion to `doc_type`, not a replacement. Reachable only via `lawService.do` (the `lawSearch.do` response omits the code) |
| `amendment_type` | ✅ XML | `<제개정구분>제정</제개정구분>`. Not in original sketch but present in XML and needed for temporality tracking |
| `enacted_date` | ✅ Sketch + XML | `<공포일자>` |
| `effective_date` | ✅ XML | `<시행일자>`. Distinct from enacted_date (공포 vs 시행) |
| `competent_authority` | ✅ XML | `<소관부처>`. Text name of overseeing ministry |
| `competent_authority_code` | ✅ XML | `<소관부처 소관부처코드="1492000">`. For reliable joins |
| `structure_code` | ⚠️ XML | `<편장절관>09010000</편장절관>`. 8-digit code indicating which structural levels (편/장/절/관) the law uses. Encoding semantics not yet verified |
| `legislation_reason` | ✅ XML (storage shape per ADR-008) | `<제개정이유내용>`. Full text of the amendment rationale. Could be large; stored inline as a `TEXT` column. ADR-008 ratified column-not-JSONB as the policy for statute-table fields |
| `source_url` | 🔶 Agreed (CLAUDE.md) | Constructed from API link |
| `content_hash` | 🔶 Agreed (CLAUDE.md) | SHA-256 of raw XML for idempotent indexing (design principle #9) |
| `effective_at` | ✅ Resolved (ADR-013) | Temporality field. Mirrors the document's legal effective timestamp. Used with `superseded_at` to compute legal effectiveness at `:as_of` |
| `superseded_at` | ✅ Resolved (ADR-013) | Temporality field. Null for the head row; set to the incoming version's `effective_at` when superseded |
| `is_head` | ✅ Resolved (ADR-013) | Latest ingested version within a `law_id` lineage. Does not mean legally effective now |
| `created_at`, `updated_at` | ✅ Auto-apply | Standard audit fields |

**Not stored (deliberate omissions)**:
- `연락부서` / `부서단위`: administrative contact info for each overseeing ministry. Not relevant to retrieval. Can be reconstructed from API if needed.
- `개정문내용`: the formal amendment text ("국회에서 의결된..."). Largely duplicates body + 부칙 content. Omitted for Phase 1.
- `법령명_한자`: identical to 한글 name for this law. May matter for older statutes. Deferred.

### structure_nodes

Represents a single node in the statute's hierarchical body. Self-referencing tree via `parent_id`.

| Field | Confidence | Source / Rationale |
|-------|-----------|-------------------|
| `node_id` | ✅ Resolved (TODO-4) | `BIGINT GENERATED ALWAYS AS IDENTITY`. Surrogate key. Stability across amendments is TODO-5 |
| `doc_id` | ✅ Resolved (TODO-4) | `BIGINT FK → legal_documents.doc_id`. Participates in the composite UK `(doc_id, node_key)` |
| `parent_id` | ✅ Sketch | `BIGINT FK` self-reference. Root nodes (편/장/조) have `parent_id = NULL` at top level. 항 → 조, 호 → 항, 목 → 호 |
| `level` | ✅ Resolved (ADR-006) | `SMALLINT` with `CHECK (level BETWEEN 1 AND 8)`. Mapping: 1=편, 2=장, 3=절, 4=관, 5=조, 6=항, 7=호, 8=목 (canonical Korean legal hierarchy) |
| `node_key` | ✅ Resolved (TODO-4 levels 1–5; ADR-012 levels 6–8) | Levels 1–5: `<조문단위 조문키="0004001">` API-native; encodes 조문가지번호 directly (e.g., `0104021` for 제104조의2). Levels 6–8: tagless positional segments appended — `{조문키}-{HH}-{NN}{BB}-{KK}`. Ordinal at 항/목; parsed `<호번호>`+`<호가지번호>` at 호. **Composite `UNIQUE (doc_id, node_key)`**. |
| `number` | ✅ Sketch + XML | Article number as text. From `<조문번호>`, `<항번호>`, `<호번호>`, `<목번호>` depending on level |
| `title` | ✅ XML | `<조문제목>`. Only present on articles (level 5). e.g., "목적", "정의", "적용범위" |
| `content` | ✅ Sketch ("text") | Renamed from sketch's `text` to avoid SQL keyword collision. Contains `<조문내용>`, `<항내용>`, `<호내용>`, or `<목내용>` |
| `sort_key` | ✅ Resolved (ADR-012) | Tagless dot-separated extension of 조문키: `{조문키}.{HH}.{NN}{BB}.{KK}`. Equivalent to `node_key` modulo separator (`-` ↔ `.`). Phase-2 follow-up: drop column per ADR-012 §Consequences. |
| `effective_date` | ✅ XML | `<조문시행일자>`. Per-article effective date — can differ from the document-level date for amended articles |
| `is_changed` | ⚠️ XML | `<조문변경여부>`. Whether this article was modified in this version. Useful for amendment tracking |
| `source_url` | 🔶 Consistent | Nullable. For nodes that have a direct API link |
| `content_hash` | 🔶 Design principle #9 | For idempotent indexing at node level |
| `effective_at`, `superseded_at`, `is_head` | ✅ Resolved (ADR-013) | Same temporality/head-version pattern as legal_documents. Legal effectiveness is computed from timestamps, not `is_head` |
| `created_at`, `updated_at` | ✅ Auto-apply | Standard audit fields |

**XML field mapping for `조문여부`**:

The XML uses `<조문여부>` to distinguish structural headings from actual articles:

| 조문여부 value | Meaning | Mapped level | Example |
|---------------|---------|-------------|---------|
| `전문` | Chapter/section heading | 1~4 (depends on context) | "제1장 총칙" |
| `조문` | Actual article | 5 (article) | "제1조(목적)" |
| (no 조문여부) | Sub-article elements | 6~8 | 항, 호, 목 |

**Note on same-number duplication**: The same `조문번호` can appear twice — once as `전문` (heading, e.g., "제2장 중대산업재해") and once as `조문` (article). The `node_key` disambiguates: `0003000` (heading) vs `0003001` (article).

### supplementary_provisions

⚠️ **This table is not in the original sketch.** Added because 부칙 (supplementary provisions) is structurally distinct from the article hierarchy:

- Free-text CDATA blocks, not hierarchical 조 → 항 → 호 → 목
- Different key structure (`부칙키` ≠ `조문키`)
- Different metadata (promulgation-specific, no `level` or `sort_key`)

**Placement**: separate table — confirmed by ADR-004 (TODO-9, 2026-04-26).

**Chunk-source status**: **not** a chunk source in Phase 1 — ADR-005
(2026-04-26). Rows are persisted and SQL-queryable but not surfaced
through the hybrid retrieval pipeline. Reasoning: cross-law mention
pattern in 일부개정 부칙 (e.g., 도서관법, 화학물질관리법) creates
retrieval-poison; the 35804/35805 rows produce near-duplicate textual
diffs; even the high-value Act 제정 부칙 has within-row mixed signal
(시행일 + 다른 법률의 개정) that needs the deferred 부칙내용 parsing
decision to clean. Reversible — revisit on the explicit triggers in
ADR-005 ("Revisit triggers"). Trade-off: phased-enforcement carve-out
queries (e.g., "50인 미만 적용 시기") cannot be answered via free-text
search in Phase 1.

| Field | Confidence | Source / Rationale |
|-------|-----------|-------------------|
| `provision_id` | ✅ Resolved (TODO-4) | `BIGINT GENERATED ALWAYS AS IDENTITY` |
| `doc_id` | ✅ Resolved (TODO-4) | `BIGINT FK → legal_documents.doc_id`. Participates in composite UK `(doc_id, provision_key)` |
| `provision_key` | ✅ Resolved (TODO-4) | `<부칙단위 부칙키="2021012617907">`. **Composite `UNIQUE (doc_id, provision_key)`** |
| `promulgated_date` | ✅ XML | `<부칙공포일자>` |
| `promulgation_number` | ✅ XML | `<부칙공포번호>` |
| `content` | ✅ XML | `<부칙내용>`. Full text, may contain multiple articles (제1조, 제2조) in free-text form |
| `created_at`, `updated_at` | ✅ Auto-apply | Standard audit fields |

---

## Open Items (TODO)

### TODO-1: ✅ RESOLVED — split annexes and forms into separate tables

**Decision**: Option B from Seheon's framing — separate `annexes` and `forms` tables.

**Empirical basis** (verified by API inspection on 2026-04-25):

| Question | Finding |
|---------|---------|
| Are annexes inline text or attachment-only? | **Inline** — `<별표내용>` CDATA contains full text. HWP/PDF/GIF are supplementary |
| Are forms inline text or attachment-only? | **Inline too** — but body is ASCII box-drawing rendering of form layout |
| Is there a discriminator field? | Yes — `<별표구분>` with values `별표` (annex) / `서식` (form) |
| Is the 별표키 distinct? | Yes — annexes end in `E` (e.g., `000100E`), forms in `F` (e.g., `000100F`) |
| Phase 1 scope volumes | 중대재해처벌법 시행령: 5 별표, 0 서식. 산안법 시행규칙 (reference): 27 별표, 111 서식 |

**Refinement of Seheon's reasoning**:
- Original framing: "forms are blank templates — metadata is enough"
- Empirical reality: forms DO have body text, but it's ASCII box-art noise that hurts retrieval quality if indexed
- Conclusion: Option B stands. The reason for excluding form bodies is **retrieval quality**, not data absence

**Schema implications applied**:
- `annexes.content_text` populated from `<별표내용>` in Phase 1 — no HWP parsing needed
- `forms` has no `content_text` column — title and metadata only
- Annex binary references live in `annex_attachments` (ADR-014):
  `source_attachment_url` preserves the upstream API value for provenance,
  while `stored_file_path` is reserved for application-controlled storage.
  These roles must not be mixed.
- Form binary references use parallel `form_attachments` with the same
  source/storage columns. The only structural difference is the owner FK
  (`annex_id` vs `form_id`); the semantic difference is that annex
  attachments support chunk-source legal content, while form attachments
  are the primary usable artifacts for metadata-only form rows.
- ADR-014 rejects a shared polymorphic `attachments` table and a shared
  nullable-owner table, aligning with ADR-003's explicit-FK pattern.
- `attachment_blobs` is deferred until deduplication, shared reuse,
  refetch lifecycle, garbage collection, or storage-backend abstraction
  becomes load-bearing.
- `chunks` source FK points to `annexes.annex_id` for annex chunks; forms are not a chunk source

**Related agreement**: DA #2 — appendices are part of the statute. phase-1-progress.md §2

### TODO-2: How to express Criminal Code references

**Current state**: undecided (DA #5, DA #11)
**Decision needed**: how to store cross-statute references (e.g., 중대재해처벌법 → 형법 specific articles)
**Options to consider**:
- A. Separate `cross_references` table — `(source_node_id, target_doc_id, target_node_id, reference_type)`. Explicit, queryable, enables graph traversal
- B. Metadata field on `structure_nodes` — JSONB array of referenced articles. Simpler but not queryable via FK
- C. Treat referenced Criminal Code articles as regular `legal_documents` + `structure_nodes` rows with a tag — no special reference mechanism, just co-existence in the same tables
- D. Combine A + C — store the Criminal Code articles in the same tables AND maintain explicit edges
**Information required to decide**:
- Complete T15: inventory of Criminal Code articles cited by the MoEL commentary
- Determine whether references are only from commentary (practical) or also from the statute body itself
- Assess retrieval impact: does the pipeline need to follow references, or just co-retrieve?
**Related agreement**: DA #5 and DA #11 in phase-1-progress.md §8

### TODO-3: ✅ RESOLVED — Phase 1 ERD scope is Option B (effectively Option A for this statute)

**Decision**: Option B — Act + Enforcement Decree + Enforcement Rules
+ appendices/forms. For 중대재해처벌법 specifically, this collapses to
**Act + 시행령 + appendices** because no 시행규칙 exists for this law.

**Empirical basis** (verified 2026-04-25): API search for `query=중대재해`
on `lawSearch.do` returns exactly two records — Act (MST=228817) and
시행령 (MST=277417). No 시행규칙 row exists in the API result set.
The Decree carries 5 별표 (annexes) and 0 서식 (forms) — see
`data/api-samples/search-중대재해.xml` and `law-277417-…xml`.

**Why no ADR**: this is a documentation cleanup, not a real decision.
The choice was forced by empirical reality (no 시행규칙 exists for
this statute), and the ERD has been produced under Option B since
the initial sketch. ADR-001 already addresses the appendices/forms
sub-decision. Promoting this to a full ADR would be ceremony without
substance. Recorded here as ✅ RESOLVED for TODO-list hygiene.

**Future-aware note**: Options C (administrative regulations) and D
(local ordinances) are explicitly out of Phase 1 scope. The
`doc_type` enum (TODO-6) should be designed to accommodate them
without schema migration if Phase 2 expands scope — that is, prefer
a representation that allows additive value extension over a rigid
PG ENUM type.

**Related agreement**: D-1 in phase-1-progress.md §6; ADR-001
(appendices/forms split, which is the substantive sub-decision
inside Option B)

### TODO-4: ✅ RESOLVED — `BIGINT IDENTITY` PK + natural-key `UNIQUE` (Option D)

**Decision**: every statute table uses `BIGINT GENERATED ALWAYS AS IDENTITY` as its primary key, with a separate `UNIQUE` constraint on the API-native natural key. Same strategy across all five tables (and forward-applied to future judicial / interpretive / practical / academic ERDs).

**Per-table specifics**:

| Table | PK | UNIQUE constraint | Natural-key source |
|-------|----|-------------------|--------------------|
| `legal_documents` | `doc_id BIGINT IDENTITY` | `UNIQUE (mst)` | `<법령일련번호>` |
| `structure_nodes` | `node_id BIGINT IDENTITY` | `UNIQUE (doc_id, node_key)` | `<조문단위 조문키>` |
| `supplementary_provisions` | `provision_id BIGINT IDENTITY` | `UNIQUE (doc_id, provision_key)` | `<부칙단위 부칙키>` |
| `annexes` | `annex_id BIGINT IDENTITY` | `UNIQUE (doc_id, annex_key)` | `<별표단위 별표키>` (E suffix) |
| `annex_attachments` | `attachment_id BIGINT IDENTITY` | none in ADR-014 | attachment rows derived from `<별표단위>` HWP/PDF/image fields |
| `forms` | `form_id BIGINT IDENTITY` | `UNIQUE (doc_id, form_key)` | `<별표단위 별표키>` (F suffix) |
| `form_attachments` | `attachment_id BIGINT IDENTITY` | none in ADR-014 | attachment rows derived from future `<별표단위>` 서식 HWP/PDF/image fields |

**Why D over A/B/C**:

1. **Idempotent ingestion (design principle #9)** — `INSERT … ON CONFLICT (mst) DO UPDATE …` is one statement per row. Options A and B (no natural UK) need a separate "find existing row" lookup, which is racier and more code.

2. **Single-column `chunks.source_id` (design principle #5)** — `chunks` references multiple source families (statute, judicial, interpretive, practical, academic). Mixed PK shapes per family would force `source_id` into a composite or text-encoded column. Uniform `BIGINT` keeps a single FK shape across all categories.

3. **pgvector index locality** — the chunks table will host the vector index. Sequential `BIGINT` joins stay buffer-cache-friendly; UUID v4 randomness fragments index reads. Negligible at Phase-1 scale, real at Phase-4.

4. **Reversible later** — adding an `external_uuid uuid UNIQUE` column on top of an existing `BIGINT` PK is non-destructive. Collapsing UUIDs into bigints later is not.

5. **Portfolio defensibility** — `BIGINT IDENTITY + natural UNIQUE` is the textbook idiomatic Postgres pattern. Reviewers parse it as competent and standard.

**Trade-off explicitly accepted**: PK values are not portable across DB rebuilds. Mitigation: the **natural key** is portable, so chunks-to-source linkage can always be re-derived via the UK after a rebuild. Chunks get rebuilt on every embedding refresh anyway, so `chunks.source_id` is never authoritative across rebuilds.

**Note on `legal_documents.law_id`**: deliberately *not* in any UNIQUE constraint. `law_id` (법령ID) is shared across versions of the same law and will collide once Phase 2 temporality is active. The version-specific identity is `mst`. When TODO-5 lands, a second UK such as `(law_id, effective_at)` may be added, but that is a TODO-5 concern.

**Related agreement**: design principle #9 (idempotent indexing), design principle #5 (multi-source by design)

### TODO-5: `node_id` retention policy across amendments

**Current state**: undecided
**Decision needed**: when a law is amended, do existing `structure_nodes` rows get updated in place or do we create new rows?
**Options to consider**:
- A. Immutable rows — each amendment creates new rows; old rows get `superseded_at` set. `node_id` is stable but version-specific. Chunks FK remains valid forever
- B. Update in place — same `node_id` is reused; content changes. Simpler but loses history; chunks point to current content only
- C. Hybrid — new row for content changes, same row for metadata-only changes. Complex but precise
**Information required to decide**:
- How frequently does 중대재해처벌법 get amended? (enacted 2021, Phase 1 domain)
- Whether the retrieval pipeline needs to answer "what did article X say on date Y?" (Phase 2+ temporality)
- Impact on chunks: if node_id changes on amendment, all chunks referencing the old node need re-indexing
**Related agreement**: design principle #4 (temporal-ready but not temporal-active), phase-1-progress.md §5

### TODO-6: ✅ RESOLVED — `doc_type` and `level` enum values + representation

**Decision**: see ADR-006 (Accepted 2026-04-28).

- `doc_type`: `TEXT` with `CHECK (doc_type IN ('법률', '대통령령',
  '총리령', '부령'))`. Formal Korean type names (not the informal
  role names 시행령/시행규칙); the API returns the formal value.
- `level`: `SMALLINT` with `CHECK (level BETWEEN 1 AND 8)`. Mapping:
  1=편, 2=장, 3=절, 4=관, 5=조, 6=항, 7=호, 8=목.
- Representation: PG ENUM rejected (rigidity, ALTER TYPE caveats);
  reference tables rejected (overkill for closed taxonomies with no
  per-row metadata); CHECK constraints chosen for both.

**Empirical basis** (verified 2026-04-28): `lawService.do` returns
`<법종구분>법률</법종구분>` (Act) and `<법종구분>대통령령</법종구분>`
(Decree); `lawSearch.do` corroborates with `<법령구분명>법률</법령구분명>`
and `<법령구분명>대통령령</법령구분명>`. 중대재해처벌법 uses level
positions {2, 5, 6, 7, 8}; the full 1–8 set is committed because the
hierarchy is statute-family-closed.

**Companion decision (ADR-007, Accepted 2026-04-28)**:
- `법종구분코드` (e.g., `A0002`, `A0007`) is captured as a sibling
  `doc_type_code TEXT NULL` column on `legal_documents`. Two
  columns express the same fact: `doc_type` is the human-facing
  canonical, `doc_type_code` is the machine-facing stable
  identifier.

**Out of scope (deferred to Phase 2)**:
- `doc_type` values for `행정규칙`, `자치법규` — pending TODO-3
  scope expansion (currently out of Phase 1).

**Verification trigger** (per ADR-006): first ingestion of any
statute carrying a 시행규칙 must verify that `<법종구분>` resolves to
exactly `'총리령'` or `'부령'` — not a ministry-prefixed variant
(e.g., `'행정안전부령'`). If observed value diverges, the CHECK set
is revisited.

**Related agreement**: phase-1-progress.md §5; ADR-002 (DB-enforced
constraint precedent); ADR-003 (early-bug-catching reasoning).

### TODO-7: Index strategy

**Current state**: undecided
**Decision needed**: which columns get B-tree indexes, partial indexes, or composite indexes
**Options to consider**:
- A. Minimal — PK + FK only (PostgreSQL creates these automatically for PK; FK indexes are manual)
- B. Retrieval-optimized — add indexes on `(doc_id, level)`, `(doc_id, sort_key)`, `is_head`, `doc_type`
- C. Deferred — add indexes based on measured query patterns after the retrieval pipeline is built
**Information required to decide**:
- Query patterns from the retrieval pipeline (not yet designed)
- Whether partial indexes on `is_head = true` or `superseded_at IS NULL` are worthwhile for head-row lookup
**Related agreement**: design principle #13 (measure first, plan second) — favors Option C

### TODO-8: ✅ RESOLVED — no JSONB on statute tables

**Decision**: see ADR-008 (Accepted 2026-04-29).

- No JSONB `metadata` column on `legal_documents`.
- No JSONB `metadata` column on `structure_nodes`.
- Forward policy: **promote** API fields to typed columns when they
  earn their keep, **omit deliberately** with a reasoned entry in the
  "Not stored" list, **retain** raw API XML responses as the
  canonical fallback for any field a future ADR decides to promote.
- `chunks.metadata` JSONB (already agreed in phase-1-progress.md §5)
  is unaffected — that JSONB serves a different role (retrieval-
  pipeline-emitted features whose schema is genuinely emergent).

**Empirical basis** (verified 2026-04-29): after mapping every
element back to the ERD — note `<항>`/`<호>`/`<목>` are *not* unmapped,
they each become a `structure_nodes` row at level 6/7/8 — the
unmapped document-level surface is small and falls cleanly into four
buckets (constant boolean flags, ERD's "Not stored" list, TODO-5
amendment-tracking fields, derivable). Not the unknown-evolving-
metadata shape that justifies a JSONB column.

**Soft dependency**: the policy presumes raw API XML responses remain
replay-available (currently `data/api-samples/` holds samples; no
formal pipeline-level retention commitment yet). ADR-008 flags this
as a revisit trigger.

**Related agreement**: ADR-007 (sibling-column-over-JSONB pattern that
this ADR generalizes); phase-1-progress.md §5 (chunks.metadata
exception).

### TODO-9: ✅ RESOLVED — keep `supplementary_provisions` as a separate table

**Decision**: Option A — `supplementary_provisions` stays as a separate
table, not merged into `structure_nodes`. See
`docs/decisions/ADR-004-supplementary-provisions-placement.md`.

**Why** (full argument in ADR-004):
- `<부칙단위>` carries `부칙공포일자` and `부칙공포번호` that have no
  analog on `<조문단위>`. Merging would force them nullable on every
  `structure_nodes` row — the same polymorphic-table pattern ADR-003
  rejected on the chunks side.
- Cardinality semantics differ: 조문 row count tracks current statute
  structure; 부칙단위 row count tracks amendment history (Decree:
  1 제정 + 5 일부개정 = 6 rows).
- Different retrieval intents — body-content queries vs effective-date
  queries — encode at the schema layer for free with two tables.

**Schema implications applied**: none — the current ERD draft already
reflects the separate-table shape. No column changes from this decision.

**Out of scope (future ADRs)**:
- Whether `supplementary_provisions` is a chunk source. ADR-003's DDL
  omits `provision_id`; the current implicit default is "not a chunk
  source," but that has not been argued explicitly. Provisional next
  ADR.
- How to internally parse `부칙내용` (제N조 inside the CDATA blob).
- Whether to add a `kind` column distinguishing 제정 부칙 vs 일부개정
  부칙 (coupled with the chunk-source question).

**Related agreement**: not in earlier sketch — raised by XML analysis on 2026-04-25, resolved 2026-04-26.

### TODO-10: ✅ RESOLVED — `parent_doc_id` self-FK on `legal_documents`

**Decision**: see ADR-009 (Accepted 2026-04-29).

- `parent_doc_id BIGINT NULL REFERENCES legal_documents(doc_id) ON DELETE RESTRICT`.
- Asymmetric CHECK: `chk_legal_documents_act_no_parent CHECK (doc_type != '법률' OR parent_doc_id IS NULL)` — Acts must have NULL parents; Decrees may have NULL (graceful degradation on title-match miss, audit by query).
- Two indexes commit ahead of TODO-7's general "measure first" deferral on use-case grounds: `ix_legal_documents_parent` (reverse traversal) and a head-row Act title partial UNIQUE (population-rule lookup uniqueness; ADR-013 replaces the old `is_current` predicate with `is_head`).
- Population rule (Phase 1): for `doc_type='대통령령'`, strip ` 시행령` from `title` and look up Act with `is_head=true`. The partial UNIQUE INDEX guarantees the lookup is unambiguous.
- Rules (총리령/부령) parent assignment is deferred — Korean 부령 제1조 typically delegates from both Act and Decree, so the heuristic needs cross-statute observation before ratification.

**Empirical basis** (verified 2026-04-29): the 법제처 OpenAPI exposes
no explicit parent-pointer field (`<상위법령>`, `<위임법령>`,
`<모법ID>` all absent). `자법타법여부` is empty for both Phase-1
documents. Title-pattern matching (`{Act_title} 시행령`) and 제1조
body text (`「{parent_title}」에서 위임된 사항`) are the only
deterministic signals; title-pattern is the primary key, 제1조 is a
non-blocking verification.

**Out of scope (deferred)**:
- Cross-statute citations (TODO-2 territory; M:N edge-list shape, different from this 1:N tree).
- Rules-parent assignment heuristic.
- 위임 phrase detection in body text (retrieval-pipeline concern, not schema).
- Phase-2 temporality of the parent relationship (TODO-5 territory).

**Related agreement**: requirement 4-2 (delegation phrases),
phase-1-progress.md §10; ADR-008 "promote when needed" policy
exercised here for the first time post-ADR-008.

---

## Differences from the Earlier-Session Sketch

### Added fields (derived from XML)

| Entity | Field | Reason |
|--------|-------|--------|
| `legal_documents` | `law_id` | API provides `법령ID` as a stable cross-version identifier. Not in sketch |
| `legal_documents` | `mst` | API provides `법령일련번호` as a version-specific identifier. Not in sketch |
| `legal_documents` | `title_abbrev` | API provides `법령명약칭`. Useful for display and search |
| `legal_documents` | `amendment_type` | API provides `제개정구분`. Needed for temporality tracking |
| `legal_documents` | `effective_date` | Distinct from `enacted_date`. 공포일자 ≠ 시행일자 (e.g., enacted 2021-01-26, effective 2022-01-27) |
| `legal_documents` | `competent_authority` / `_code` | API provides 소관부처. Useful for filtering |
| `legal_documents` | `structure_code` | API provides 편장절관 code. Determines which structural levels exist |
| `legal_documents` | `legislation_reason` | API provides 제개정이유. Large text; storage approach is TODO-8 |
| `structure_nodes` | `doc_id` FK | Implicit in sketch (nodes belong to a document) but not explicit |
| `structure_nodes` | `node_key` | API's native identifier (조문키). Enables re-fetch and provenance tracking |
| `structure_nodes` | `title` | API provides 조문제목 (e.g., "목적", "정의"). Not in sketch |
| `structure_nodes` | `effective_date` | Per-article 조문시행일자. Can differ from document-level date |
| `structure_nodes` | `is_changed` | API provides 조문변경여부. Useful for amendment tracking |

### Added fields (from earlier agreements, not in sketch)

| Entity | Field | Agreement source |
|--------|-------|-----------------|
| Both | `effective_at`, `superseded_at`, `is_head` | Temporality/head-version readiness (ADR-013; legal effectiveness is computed via timestamp predicates) |
| Both | `source_url`, `content_hash` | CLAUDE.md §4 (immediate next steps) |
| Both | `created_at`, `updated_at` | Standard audit fields (auto-apply) |

### Renamed fields

| Sketch | ERD | Reason |
|--------|-----|--------|
| `text` | `content` | `text` is a PostgreSQL type name. Avoidance of ambiguity |

### Added entity

| Entity | Reason |
|--------|--------|
| `supplementary_provisions` | 부칙 is structurally different from the article hierarchy (free text, different keys). Not in sketch. Confirmed by ADR-004 (TODO-9 resolved 2026-04-26) |
| `annexes` | 별표 contains substantive provisions (penalty schedules, scope qualifiers, etc.) and must be a first-class chunk source. Inline text confirmed in API (TODO-1 resolved) |
| `annex_attachments` | Annex HWP/PDF/image references and downloaded binary metadata. Supports annex legal content but is not itself indexed. Separates upstream provenance (`source_attachment_url`) from application-owned storage (`stored_file_path`) per ADR-014 |
| `forms` | 서식 carries metadata + downloadable files only. Body content is ASCII box-art unsuitable for retrieval. Excluded from chunks (TODO-1 resolved) |
| `form_attachments` | Form HWP/PDF/image references and downloaded binary metadata. Primary usable artifacts for metadata-only form rows; not chunk sources |

### Sketch fields retained as-is

| Field | Status |
|-------|--------|
| `doc_id`, `title`, `law_number`, `doc_type`, `enacted_date` | ✅ Unchanged |
| `node_id`, `parent_id`, `level`, `number`, `sort_key` | ✅ Unchanged |

---

## Next Steps

1. **Resolve remaining TODOs** — TODO-2 (Criminal Code refs, blocked on T15), TODO-5 (amendment retention, Phase-2 temporality), TODO-7 (index strategy, deferred-by-design — though ADR-009 has committed two indexes ahead of the general ratification). TODO-1, TODO-3, TODO-4, TODO-6, TODO-8, TODO-9, TODO-10 are resolved
2. **Write DDL** — convert this ERD to `migrations/001_statute_tables.sql` once the remaining TODOs are resolved (or once a "Phase-1 DDL freeze" decision is made — TODO-2 and TODO-5 may not block Phase 1 if they ship as additive Phase-2 ALTERs)
4. **Design Document Parsing Pipeline** — XML → `legal_documents` + `structure_nodes` mapping logic; must include the ADR-009 ingestion-order rule (Acts before Decrees, or second-pass parent resolution)
5. **ERDs for other categories** — judicial (`case_laws`), interpretive (`interpretations`), practical/academic (`commentaries`). Each is a separate task
6. **Integration with chunks table** — confirm FK granularity and stability guarantees

---

## Self-Check

- [x] Mermaid block uses valid erDiagram syntax
- [x] Every entity has a PK
- [x] All FKs explicitly marked
- [x] Self-reference shown for `structure_nodes`
- [x] All 8 required open items captured as TODOs (plus 2 additional: TODO-9, TODO-10)
- [x] No silent decisions — all additions marked with confidence levels
- [x] No conflict with phase-1-progress.md agreements
- [x] All items carry confidence markers
- [x] No invented terminology
- [x] No unverified numbers stated as fact
- [x] Scope limited to statute (성문규범) category only
