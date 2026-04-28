# ADR-004 — Keep `supplementary_provisions` as a separate table (not merged into `structure_nodes`)

- **Status**: Accepted
- **Date**: 2026-04-26
- **Context layer**: Statute (성문규범) ERD
- **Resolves**: TODO-9 in `docs/legal-erd-draft.md`
- **Depends on / aligned with**: ADR-001 (split-table pattern for substantive
  vs non-substantive content), ADR-002 (already names
  `supplementary_provisions` as one of five statute tables under the BIGINT
  IDENTITY scheme), ADR-003 (split FK columns on chunks — adding a future
  source column is a known, accepted extension point)
- **Out of scope (downstream decisions, not decided here)**:
  1. ~~Whether `supplementary_provisions` is a chunk source.~~
     **Resolved by ADR-005 (2026-04-26)**: not a chunk source in
     Phase 1.
  2. How to internally parse `부칙내용` (제N조 sub-structure inside the
     CDATA blob). Parsing/chunking decision, separate from placement.
     **Still deferred** — only becomes live if ADR-005 is overturned.
  3. Whether to distinguish 제정 부칙 vs 일부개정 부칙 with a `kind`
     column. **Still deferred** — only becomes live if ADR-005 is
     overturned (it was needed only for the rejected Option B).

## Context

The 법제처 OpenAPI returns supplementary provisions (부칙) under a top-level
`<부칙>` element that is a **sibling of `<조문>`**, not nested inside it.
Inside `<부칙>` are one or more `<부칙단위>` rows, each with its own
attributes:

```xml
<부칙>
  <부칙단위 부칙키="2021012617907">
    <부칙공포일자>20210126</부칙공포일자>
    <부칙공포번호>17907</부칙공포번호>
    <부칙내용><![CDATA[부칙 <제17907호,2021.1.26> ...]]></부칙내용>
  </부칙단위>
</부칙>
```
(`docs/api-samples/law-228817-중대재해처벌법.xml`, lines 655–680)

The ERD draft (`docs/legal-erd-draft.md`) already proposes
`supplementary_provisions` as a separate table. This ADR exists to **confirm
or overturn that default**, not to introduce it. Because TODO-9 was raised
explicitly as a question rather than treated as resolved, ADR-002's
five-table list and ADR-003's two-FK-column chunks DDL are working under an
unstated assumption that ADR-004 needs to make load-bearing.

The question matters because:

- The two model shapes lead to **different ingestion code paths**, different
  query patterns ("body content only" vs "all content"), and different
  consequences for ADR-003's CHECK + generated `source_type`.
- 부칙 is **not just metadata**. The original (제정) 부칙 contains the
  effective-date clauses (`제1조(시행일)`) and any phased-enforcement
  carve-outs — which are real user-query targets even if the chunk-source
  decision is deferred.
- The current ERD draft, ADR-002, and ADR-003 are all consistent with the
  separate-table shape; merging is the option that requires more downstream
  rewrites if chosen.

## Empirical basis (verified 2026-04-26)

| Question | Finding | Source |
|----------|---------|--------|
| Is `<부칙>` nested inside `<조문>`? | No — it is a sibling element under the document root. | Act XML lines 654–680, Decree XML lines 791–820 |
| Does `부칙단위` carry attributes that 조문단위 lacks? | Yes — `부칙공포일자` (date), `부칙공포번호` (announcement number). 조문단위 has neither. | Act XML lines 656–658 |
| Are the natural-key formats identical or different? | **Different.** `조문키` is a 7-digit zero-padded code (`"0001000"`, `"0001001"`); `부칙키` is a 13-digit `YYYYMMDDNNNNN` code (`"2021012617907"`). | Act XML lines 59, 656; Decree XML line 793 |
| How many 부칙단위 per document, in Phase-1 scope? | Act: 1 (제정 only). Decree: 6 (1 제정 + 5 일부개정 by other-law amendments). | Decree XML lines 792–886 (5 of 6 amending entries inspected) |
| Does the 제정 부칙 carry retrieval-relevant content? | Yes — Act 부칙 line 662 contains the phased-enforcement 시행일 clause ("공포 후 1년이 경과한 날… 50명 미만… 공포 후 3년"). This is a real user-query target. | Act XML lines 660–675 |
| Do 일부개정 부칙 carry retrieval-relevant content? | Mostly **no** — they are framed as "다른 법령의 개정" with most clauses elided ("①부터 ⑭까지 생략"), keeping only the clause that touches this statute. Low signal-to-noise for retrieval. | Decree XML lines 805–833, 835–860, 862–884 |
| Is `부칙내용` element-structured XML or a single text blob? | Single CDATA blob; internal sub-structure (제N조 markers) exists as text only. | Act XML lines 659–678 |

## Decision

Keep `supplementary_provisions` as a **separate table**. Do not merge
`부칙단위` rows into `structure_nodes` under a sentinel `level` value or a
discriminator column.

The current ERD draft schema already reflects this:

```
supplementary_provisions {
  provision_id BIGINT IDENTITY PK
  doc_id BIGINT FK → legal_documents.doc_id
  provision_key TEXT          -- "부칙키"; UNIQUE(doc_id, provision_key)
  promulgated_date DATE       -- 부칙공포일자
  promulgation_number INT     -- 부칙공포번호
  content TEXT                -- 부칙내용
  created_at, updated_at
}
```

This ADR endorses the existing draft shape; it does not add columns to it.

## Options considered

| Option | Shape | Verdict |
|--------|-------|---------|
| **A** | **Separate `supplementary_provisions` table** | **accepted** |
| B | Merge into `structure_nodes` with `level` sentinel (e.g., `level=0` or `level=9`) | rejected — see below |
| C | Merge into `structure_nodes` AND parse 부칙내용 into child rows (제N조 → child node) | rejected — strictly worse than B; locks an unrelated parsing decision into the placement decision |

### Why A over B (the only viable merge variant)

1. **Required attributes diverge.** `부칙공포일자` and `부칙공포번호` are
   meaningful on every 부칙단위 row and meaningless on every 조문단위 row.
   Merging forces both columns nullable on `structure_nodes`, with the
   NULL set strictly correlated to the discriminator. That is exactly the
   "polymorphic table" pattern ADR-003 rejected for the chunks side
   ("integrity moves to application code"); rejecting it on chunks while
   adopting it here would be inconsistent. A JSONB sidecar avoids the
   nullable columns but introduces a *less queryable* shape than two real
   columns on a real table — strictly worse than the natural fit.

2. **Cardinality semantics are categorically different.** 조문단위 row
   count is a function of *current statute structure* — stable after
   enactment, modified in place by amendments. 부칙단위 row count is a
   function of *amendment history* — strictly monotonic, one row per
   announcement event. The Decree's 1+5 = 6 부칙단위 rows are 5 distinct
   amendment events plus the 제정. Mixing this growth pattern with the
   structurally-stable 조문 family in one table obscures both
   denormalization-vs-temporality discussions and downstream
   provenance/audit queries.

3. **Granularity asymmetry — different ingestion paths regardless.**
   조문단위 has nested XML children (`<항>`, `<호>`, `<목>`) that map onto a
   parser tree directly. 부칙내용 is a single CDATA blob whose internal
   제N조 structure exists only as text. The two are fundamentally
   different parser-side. The schema can mirror that asymmetry honestly
   (separate tables) or hide it behind a discriminator and re-create it in
   ingestion code (merged). Honest is better.

4. **Retrieval intent diverges.** Body-content queries ("제4조 안전조치
   의무가 무엇인가?") want 조문 only. Effective-date queries ("이 법은 언제
   시행되나요?", "50인 미만 사업장은 언제부터 적용?") want 부칙 only. With
   merged storage, every body-content query needs a `WHERE node_type =
   'article'` filter and every effective-date query needs the inverse.
   Two tables encode this distinction at the schema layer for free. (This
   is upstream of the chunks-source decision: even if 부칙 is *never*
   indexed for retrieval, structured queries against the ERD will still
   ask the same intent-typed questions.)

5. **Already named separately upstream.** ADR-002 lists
   `supplementary_provisions` as one of five statute tables and assigns it
   `provision_id BIGINT IDENTITY PK` plus `UNIQUE(doc_id, provision_key)`.
   ADR-003's chunks DDL omits any `provision_id` FK column — consistent
   with the current default that 부칙 is a separate table and (today) not
   a chunk source. Choosing B now triggers a cascading rewrite of those
   ADRs and the ERD draft, for no offsetting modeling benefit.

### Steelman of B that I considered and reject

> "Reduces table count from 5 to 4. Single search index over 'all body
> content' via `WHERE node_type IN ('article', 'supplementary')`."

The table-count argument is cosmetic — Postgres does not care about 4 vs
5 tables, and ingestion code will branch on `<조문>` vs `<부칙>` regardless
of where the rows land. The single-search-index argument is upstream of
the chunks-source decision (which this ADR explicitly does *not* take):
even if both end up indexed, the chunks side already supports unified
search across multiple source tables (ADR-003), so source-table
multiplicity is not what drives index unification.

### Why C (merge + parse 부칙내용 into children) is rejected outright

C piles a parsing decision (how to chunk 부칙내용 into 제N조 children)
onto a placement decision. The right time to decide parsing is when the
chunks-source ADR is drafted, with an explicit budget for regex
robustness vs payoff. Conflating the two is scope creep.

## Consequences

- ERD draft, ADR-002, and ADR-003 stay coherent. No cascading rewrites.
- `supplementary_provisions` keeps its current proposed shape:
  `provision_id` PK, `(doc_id, provision_key)` UK, plus
  `promulgated_date`, `promulgation_number`, `content`, audit columns.
- DDL for `supplementary_provisions` becomes a single CREATE TABLE in
  the next migration pass, parallel to `structure_nodes` and `annexes`.
- The chunks-source question is now isolated and addressable on its own
  merits in a follow-up ADR. If 부칙 *does* become a chunk source,
  ADR-003 grows by one column (`provision_id BIGINT REFERENCES
  supplementary_provisions(provision_id) ON DELETE RESTRICT`), one branch
  in the CHECK, and one branch in the generated `source_type` — exactly
  the per-source-family extension pattern ADR-003 already accepts.
- If a future ADR splits original vs amending 부칙 (likely necessary for
  retrieval quality given the empirical signal-to-noise gap), that split
  is *additive on this table*, not retroactive — a `kind` column or a
  filtered chunk-source policy lands cleanly.

## What is checked vs. what is still open

**Checked (this ADR):**

- Structural difference between `<조문단위>` and `<부칙단위>` in the API
  payload (different parents, different attributes, different natural-key
  formats). Verified against both Phase-1 sample files.
- Multi-row cardinality of `<부칙단위>` per document, including the
  amendment-driven growth pattern (verified on Decree, 6 entries).
- Retrieval relevance of the 제정 부칙 content (시행일 clauses present in
  the Act 부칙).

**Still open (deferred to other ADRs):**

- **Chunk-source status of `supplementary_provisions`.** Provisional next
  ADR. Strongest argument *for* indexing: the Act's 시행일 clause is a
  high-value retrieval target. Strongest argument *against* indexing
  uniformly: 5 of 6 부칙단위 rows in the Decree are noisy "다른 법령의
  개정" entries with elided content. A selective-indexing policy is
  likely; this ADR does not pre-decide it.
- **Internal parsing of `부칙내용`.** Today `content` is a single TEXT
  blob. Whether to extract the 제N조 sub-structure into rows or chunks
  is a parsing/granularity decision, not a placement one.
- **Disjointness of `조문키` and `부칙키` namespaces.** The two formats
  are observably different (7-digit numeric vs 13-digit
  YYYYMMDDNNNNN), but cross-family collision has not been *proved*
  impossible — only argued from format inspection. Since the keys live
  in two separate UNIQUE constraints on two separate tables, this is
  not load-bearing for ADR-004; flagging here for the record.

## References

- `docs/legal-erd-draft.md` — TODO-9 at lines 401–413; current
  `supplementary_provisions` block in the Mermaid diagram
- `docs/decisions/ADR-001-split-annexes-and-forms.md` — split-table
  precedent (substantive vs non-substantive content)
- `docs/decisions/ADR-002-identifier-strategy.md` — names
  `supplementary_provisions` and assigns its identifier strategy
- `docs/decisions/ADR-003-chunks-fk-shape.md` — chunks-side extension
  pattern that a future "부칙 as chunk source" ADR would plug into
- `docs/api-samples/law-228817-중대재해처벌법.xml` — Act 부칙 (1
  부칙단위; 시행일 evidence)
- `docs/api-samples/law-277417-중대재해처벌법시행령.xml` — Decree 부칙
  (6 부칙단위; amendment-cadence evidence)
