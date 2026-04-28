# ADR-009 — Act↔Decree linkage via `parent_doc_id` self-FK on `legal_documents`

- **Status**: Accepted
- **Date**: 2026-04-29
- **Context layer**: Statute (성문규범) ERD
- **Resolves**: TODO-10 in `docs/legal-erd-draft.md` (how to express
  the relationship between a 법률 and its 시행령 / 시행규칙)
- **Depends on / aligned with**: ADR-002 (BIGINT IDENTITY PK + natural-
  key UNIQUE pattern — this ADR uses the IDENTITY PK as the FK target),
  ADR-006 (formal `doc_type` values 법률/대통령령/총리령/부령 — used
  in the population rule), ADR-008 (no JSONB on statute tables — this
  ADR adds a typed column, consistent with ADR-008's "promote when
  needed" policy)
- **Out of scope (not decided here)**:
  1. Cross-statute references (e.g., 중대재해처벌법 → 형법 articles).
     That is TODO-2 territory; different cardinality (M:N) and different
     semantics (citation, not delegation).
  2. 시행규칙 (`총리령` / `부령`) parent assignment when delegated by
     both Act and Decree. Not present in 중대재해처벌법's Phase-1
     scope (no 시행규칙 exists for this statute). Deferred until the
     first 시행규칙-bearing statute enters scope.
  3. 위임 phrase detection in body text ("그 구체적 사항은 대통령령으로
     정한다"). That is a retrieval-pipeline concern (delegation-following
     query expansion), not a schema concern. The schema-level pointer
     enables the pipeline; the pipeline owns the detection logic.
  4. Phase-2 temporality of the parent relationship (does an old version
     of the Decree point to an old version of the Act?). TODO-5 territory;
     for Phase 1 with `is_current = true` for all rows, this collapses
     to "current Decree → current Act."

## Context

The 법제처 OpenAPI does not return any field that explicitly points
from a 시행령 (Enforcement Decree) back to its parent 법률 (Act).
Verified empirically against the two Phase-1 documents:

| Document | `법령ID` | `법령명_한글` | `법령구분명` |
|---------|---------|--------------|-------------|
| Act | `013993` | `중대재해 처벌 등에 관한 법률` | `법률` |
| Decree | `014159` | `중대재해 처벌 등에 관한 법률 시행령` | `대통령령` |

The two `법령ID` values are unrelated — `014159` is not a derivative
of `013993`. There is no `<상위법령>`, no `<위임법령>`, no `<모법ID>`,
no other field that crosses the boundary.

What the API does provide:

1. **Title naming convention** — exact pattern `{Act_title} 시행령`
   in `법령명_한글` (and `{Act_title_abbrev} 시행령` in
   `법령명약칭`). Highly reliable in Korean legal practice for
   modern statutes.
2. **Body text reference** — the Decree's 제1조(목적) reads
   `이 영은 「중대재해 처벌 등에 관한 법률」에서 위임된 사항과
   그 시행에 필요한 사항을 규정함을 목적으로 한다`. This is the
   standardized 위임 (delegation) phrase that names the parent Act.
3. **`자법타법여부`** field on `lawSearch.do` is empty for both
   Phase-1 documents, so it is not a parent-linkage indicator
   (it tracks amendment-side relationships, not delegation).

The decision is whether to materialize this relationship as a
schema-level pointer (and which shape), or to leave it as an
inferred-at-query-time relationship.

The decision matters because:

- **Retrieval pipeline use case.** Requirement 4-2 (delegation
  phrases) calls for the pipeline to "follow delegation" when an
  Act article delegates to its Decree. Without a schema-level
  pointer, this requires title-pattern matching at query time on
  every delegation-phrase hit — slower, harder to audit, and
  fragile to edge cases.
- **Eval-harness use case.** Quantitative evaluation of "did the
  retriever surface the right Decree article for this Act-rooted
  query?" requires deterministic Act↔Decree linkage. Title
  matching at eval time conflates retrieval quality with linkage
  resolution quality.
- **Forward applicability.** The same shape is needed for the
  other category ERDs once they enter scope (case_laws may have
  parent-statute pointers; interpretations cite specific
  legal_documents). Resolving the pattern here travels.

## Empirical basis (verified 2026-04-29)

Linkage signals available in the API:

| Signal | Reliability | Source |
|--------|-------------|--------|
| `법령명_한글` ends with `시행령` and the prefix matches an Act's `법령명_한글` | High for modern statutes | Decree XML line "중대재해 처벌 등에 관한 법률 시행령" |
| `법령명약칭` ends with ` 시행령` | High when `title_abbrev` is populated for both | "중대재해처벌법 시행령" / "중대재해처벌법" |
| 제1조 text contains `「{parent_title}」에서 위임된 사항` | High; standardized delegation phrase | Decree XML 제1조 |
| `자법타법여부` field | None (empty in samples) | search XML |
| `소관부처` overlap | Suggestive only | Both share 고용노동부 + others |

The title-pattern signal is by far the strongest and is sufficient
for deterministic Phase-1 ingestion. The 제1조 body-text signal is
a secondary verification that can be checked at parse time but is
not needed as a primary key.

Cardinality:

| Document type | Phase-1 parent | Phase-2+ parent (Rules) |
|---------------|----------------|-------------------------|
| 법률 (Act) | NULL | NULL |
| 대통령령 (Decree) | the Act | the Act |
| 총리령/부령 (Rules) | (n/a — none in Phase-1 scope) | the Act *or* the Decree, depending on which delegates |

For Phase 1, the relationship is a simple two-level tree
(Act → Decree). For Phase 2+ Rules, the parent assignment becomes
ambiguous and is explicitly out of scope here.

## Decision

Add a self-referencing FK column on `legal_documents`, plus an
asymmetric CHECK, plus the two indexes that the column's read path
needs:

```sql
-- Column + FK
legal_documents.parent_doc_id  BIGINT NULL
                                REFERENCES legal_documents(doc_id)
                                ON DELETE RESTRICT

-- Asymmetric CHECK: Acts MUST have NULL parents.
-- Decrees MAY have NULL parents (graceful degradation on title-match miss).
CONSTRAINT chk_legal_documents_act_no_parent
  CHECK (doc_type != '법률' OR parent_doc_id IS NULL)

-- Reverse-traversal index (Act → its Decree[s]).
-- Partial because most non-Act rows are populated; index hot path only.
CREATE INDEX ix_legal_documents_parent
  ON legal_documents (parent_doc_id)
  WHERE parent_doc_id IS NOT NULL;

-- Lookup-key uniqueness for the population rule.
-- Without this, two Acts sharing an exact title (rare but real
-- in 법제처 data — e.g., a repealed and a current statute coexisting
-- after Phase-2 temporality lands) silently corrupt the parent
-- assignment of a Decree. Hard-fail at ingest instead.
CREATE UNIQUE INDEX ux_legal_documents_current_act_title
  ON legal_documents (title)
  WHERE doc_type = '법률' AND is_current = true;
```

**Semantics**: `parent_doc_id` points to the **immediately delegating
document** for this row.

- `doc_type = '법률'` → `parent_doc_id = NULL` (enforced by CHECK).
- `doc_type = '대통령령'` → `parent_doc_id` = the doc_id of the Act
  delegating to this Decree.
- `doc_type IN ('총리령', '부령')` → `parent_doc_id` = the Act *or*
  the Decree, per a Phase-2 sub-decision when Rules enter scope.
  (For Phase 1 with no 시행규칙 in 중대재해처벌법, this case does
  not occur.)

**Why an asymmetric CHECK, not a symmetric one.** Two halves of the
constraint were considered:

| Half | Expression | Verdict |
|------|------------|---------|
| Acts → NULL parent | `CHECK (doc_type != '법률' OR parent_doc_id IS NULL)` | **Adopted.** Catches misclassifications cheaply (e.g., a row mis-typed as `법률` that somehow inherited a parent FK). By-definition never violated by clean data, so zero ingestion cost. |
| Non-Acts → non-NULL parent | `CHECK (doc_type = '법률' OR parent_doc_id IS NOT NULL)` | **Rejected.** Pre-modern or irregularly-titled statutes may not match the title pattern at ingestion. Graceful degradation (NULL with audit warning) is preferred over ingestion-blocking. |

Adopting the strong half while leaving the weak half soft gets
both safety (Acts can't accidentally be parented) and graceful
degradation (Decrees that don't match a known Act land with NULL
+ warning rather than failing the insert).

The "ALTER on Phase-2 doc_type expansion" objection considered
earlier is dropped: ALTERing a CHECK is essentially free in
PostgreSQL, and the CHECK above is doc_type-direction-asymmetric in
a way that survives 행정규칙 / 자치법규 additions without revision
(those are non-법률, so they fall into the "may have NULL" branch
that's not being asserted).

**Why `ON DELETE RESTRICT`.** The expected lifecycle pattern for
`legal_documents` is **soft-delete via `is_current = false`** under
Phase-2 temporality, *not* hard `DELETE`. Hard-deleting a parent
Act with extant Decrees would orphan the children, which under any
plausible domain semantics is wrong:

| ON DELETE | Behavior on Act hard-delete | Verdict |
|-----------|------------------------------|---------|
| `CASCADE` | Decrees deleted with the Act | **Rejected.** Decrees can outlive their Acts (Act repealed, Decree still in force for an interval) — see Revisit triggers. CASCADE destroys data. |
| `SET NULL` | Decree's `parent_doc_id` set to NULL silently | **Rejected.** Silent orphaning hides a likely operator error (or migration bug). |
| `RESTRICT` | Hard-delete fails with FK violation | **Adopted.** Forces the operator to surface their intent (re-parent? mark Decrees `is_current=false` first? something else?). Aligned with the soft-delete-only lifecycle. |

This is consistent with the observation that the corpus uses
`is_current` flips (Phase-2 work) for retirement, not row deletion.
If a hard-delete escape hatch is ever needed (e.g., GDPR-style data
purge for an erroneously ingested document), it is a privileged
operation that warrants the FK violation as a forcing function.

**Population rule (Phase 1)**: at ingestion, after the row's
`doc_type`, `title`, and `title_abbrev` are populated:

1. If `doc_type = '법률'`: `parent_doc_id = NULL`. Done. (CHECK
   would block any other value.)
2. If `doc_type = '대통령령'`:
   - Compute `candidate_act_title = title - " 시행령"` (strip
     trailing " 시행령").
   - Look up Act row via
     `SELECT doc_id FROM legal_documents WHERE title = :candidate_act_title AND doc_type = '법률' AND is_current = true`.
   - The partial UNIQUE INDEX
     `ux_legal_documents_current_act_title` guarantees this query
     returns 0 or 1 row — never ambiguous.
   - If 1 row found: set `parent_doc_id = found_doc_id`.
   - If 0 rows found: log an ingestion warning, leave
     `parent_doc_id = NULL`. (CHECK does not block this — see
     "asymmetric CHECK" above.)
   - Verification: parse the Decree's 제1조 content; if it does
     not contain a reference to the matched Act's title, log a
     warning. (Verification is non-blocking.)
3. If `doc_type IN ('총리령', '부령')`: defer per "Out of scope" #2.

The partial UNIQUE INDEX `ux_legal_documents_current_act_title`
(scoped to `doc_type='법률' AND is_current=true`) is the lookup
key's structural guarantee — the parent-Act lookup is always
unambiguous within the current corpus. If two Acts ever attempt to
coexist with the same title (e.g., during Phase-2 temporality work
where `is_current=true` could in theory be wrongly set on multiple
rows), ingestion hard-fails on the index violation rather than
silently picking one.

## Options considered

| Option | Verdict |
|--------|---------|
| A. No explicit FK — rely on title pattern matching at query time | rejected — see "vs. A" |
| **B. `parent_doc_id` self-FK on `legal_documents`** | **accepted** |
| C. Separate `document_relations` table — `(source_doc_id, target_doc_id, relation_type)` | rejected — see "vs. C" |
| D. Both `parent_doc_id` (cached) and `document_relations` (canonical) | rejected — premature on the M:N side |

### Why B over A — the strongest competitor

A ("no FK, just match titles at query time") is the steelman because
the relationship is inferable, the title pattern is highly reliable,
and Phase 1 has only two documents — the storage and code cost of
a column to hold a derivation seems disproportionate.

The arguments **for** A:

1. **The relationship is fully derivable** from `title` /
   `title_abbrev`. A query that needs it can `JOIN` on a `LIKE`
   pattern. No schema change.
2. **YAGNI**. Until the retrieval pipeline is built, no query
   actually exercises the relationship. Adding a column "in case"
   is the kind of preemptive design the working agreements warn
   against.
3. **Phase-1 is two documents**. The whole question is about a
   relationship with cardinality 1.

The arguments **against** A (and why B wins):

1. **Same asymmetry as ADR-007**. Resolving the parent at
   ingestion time is one extra `SELECT … WHERE title = …` per
   non-Act document. Resolving it at query time is a `LIKE` join
   on every query that touches the relationship — at every retrieval
   pipeline call, at every eval run, at every audit query. The
   cost shape is "once at ingest" vs "every query."
2. **Title matching at query time is fragile.** It works for
   "compute the parent from this Decree row" but breaks for
   "give me all children of this Act" without knowing the children
   exist. The reverse traversal (Act → its Decree[s]) needs an
   index. A typed FK column is indexable cleanly; a `LIKE` on
   `title` requires a trigram index or full-text and is still
   not a true equality lookup.
3. **Eval traceability**. Quantitative evaluation distinguishes
   linkage-resolution quality from retrieval quality. With B, the
   linkage is resolved deterministically at ingestion; with A,
   every eval result couples both. Conflating them makes
   retrieval-pipeline regressions hard to attribute.
4. **The relationship is a fact about the corpus, not a query
   parameter.** Schema-level facts belong in the schema. The
   working agreements' "future-aware" principle: the cost of
   adding `parent_doc_id` later (after a year of eval data
   anchored to title-LIKE assumptions) is higher than the cost of
   adding it now.

### Why B over C — separate `document_relations` table

C would be `document_relations(source_doc_id, target_doc_id,
relation_type)` with `relation_type = 'delegated_by'` or
`'parent_of'`.

Why C loses:

1. **Cardinality is 1:N, not M:N.** A Decree has exactly one
   parent Act. An Act has 0..N children. This is a tree, not a
   graph, and trees map cleanly to self-FKs. Edge-list tables
   earn their keep when the relationship is M:N (one document
   participates in many relationships of varying types) — that is
   TODO-2's shape (cross-statute citations), not TODO-10's.
2. **Adds a JOIN forever** for queries that need the parent.
   With B, `SELECT parent_doc_id FROM legal_documents WHERE
   doc_id = :decree_id` is a single-row read. With C, every parent
   resolution is a JOIN.
3. **Two different relationship questions answered by two
   different tables is the right shape.** TODO-2 (cross-statute
   citations) will likely produce something edge-list-shaped.
   TODO-10 (Act↔Decree delegation) is hierarchical. Keeping them
   separate keeps each schema element's role unambiguous: the
   self-FK is "delegated by," the future M:N table is "cites."
4. **Reversible.** If a future requirement surfaces a true M:N
   delegation pattern (e.g., a statute delegated by multiple Acts
   simultaneously — none observed in the corpus), introducing
   `document_relations` then is non-destructive: `parent_doc_id`
   becomes either deprecated or a denormalized cache. Going the
   other direction (drop `document_relations`, introduce
   `parent_doc_id` later) is harder because the FK contract
   already exists in queries.

### Why B over D — both `parent_doc_id` and `document_relations`

D would have `parent_doc_id` as the primary pointer and
`document_relations` as a richer M:N layer for everything else.

Why D loses **as primary**:

1. **No M:N relationship is in scope yet.** TODO-2 (Criminal Code
   citations) is blocked on T15 commentary inventory and is
   Phase-2-ish. Adding `document_relations` now is preemptive.
2. **Premature shape.** The schema of `document_relations` (what
   relation types? what edge metadata?) is genuinely
   underdetermined until TODO-2 lands. Designing it now is a
   guess.

D is held as the natural target shape *if* TODO-2 introduces
`document_relations`. At that point, ADR-009's `parent_doc_id` and
TODO-2's `document_relations` coexist with clear role separation
(self-FK = delegation; edge-list = citations). No revision of
ADR-009 is required.

## Trade-offs accepted

- **Asymmetric CHECK enforcement.** The Acts→NULL half is enforced
  by `chk_legal_documents_act_no_parent`. The Decrees→non-NULL half
  is *not* enforced; a Decree row with `parent_doc_id IS NULL` is a
  legal but auditable state. Audit by a periodic
  `WHERE doc_type IN ('대통령령', '총리령', '부령') AND parent_doc_id IS NULL`
  query on the corpus.
- **Title-match dependency at ingestion.** Population requires the
  Act row to be present in `legal_documents` before the Decree row
  is ingested. The ingestion pipeline must order Act before Decree
  (or perform a second-pass resolution after all rows are loaded).
  This is a small ingestion-side ordering constraint, not a schema
  constraint.
- **Edge cases default to NULL.** If a Decree title doesn't match
  any Act (mis-spelled, abbreviated unusually, pre-modern
  statute), `parent_doc_id` lands NULL with a warning. This is the
  graceful-degradation choice; it requires that downstream
  consumers handle NULL.
- **Reverse traversal is `WHERE parent_doc_id = :act_id`.** No
  ergonomic helper; consumers run the query directly. Acceptable
  given Phase 1's small corpus and Phase 2+'s indexable column.

## Consequences

- ERD draft `legal_documents` block gains a new column row:
  `parent_doc_id BIGINT NULL FK → legal_documents.doc_id`.
- ERD draft Mermaid diagram gains a self-referencing relationship
  on `legal_documents` (analogous to the existing self-ref on
  `structure_nodes`).
- ERD draft TODO-10 flips to ✅ RESOLVED with a pointer to ADR-009.
- ERD draft `Open Items` count drops from 4 (TODO-2, 5, 7, 10) to 3
  (TODO-2, 5, 7).
- Ingestion pipeline (when designed) must include the Phase-1
  population rule above. Not a Phase-1 schema concern, but ADR-009
  records the rule so the pipeline design has a target.
- DDL: when `migrations/001_statute_tables.sql` is written, the
  following land inline on `CREATE TABLE legal_documents` (and as
  separate index statements where required by PostgreSQL syntax).
  Same DDL convention as ADR-006 / ADR-007:
  - Column: `parent_doc_id BIGINT NULL REFERENCES legal_documents(doc_id) ON DELETE RESTRICT`.
  - Constraint: `chk_legal_documents_act_no_parent CHECK (doc_type != '법률' OR parent_doc_id IS NULL)`.
  - Index: `ix_legal_documents_parent` on `(parent_doc_id) WHERE parent_doc_id IS NOT NULL` (reverse-traversal hot path; eval-harness invocations and delegation-following queries hit this).
  - Index: `ux_legal_documents_current_act_title` UNIQUE on `(title) WHERE doc_type = '법률' AND is_current = true` (population-rule lookup-key uniqueness).
- TODO-7 (index strategy) — ADR-009 commits two indexes
  (`ix_legal_documents_parent`, `ux_legal_documents_current_act_title`)
  ahead of the general "measure first" deferral. These earn their
  keep on use-case grounds: reverse traversal is on the eval/retrieval
  hot path, and the partial UNIQUE backs a correctness-critical
  ingestion lookup. TODO-7's broader index-strategy ratification
  remains open.
- ADR-008's "promote when needed" policy is exercised here for the
  first time post-ADR-008: a column was added to address a real
  Phase-1 use case (delegation-following retrieval). The forward
  policy is consistent.

## Verification once accepted

1. ERD draft TODO-10 marked ✅ RESOLVED with ADR-009 pointer; "Open
   Items" reduced to TODO-2, 5, 7.
2. `legal_documents` block in ERD gains the `parent_doc_id` row
   with the role-naming comment.
3. Mermaid diagram gains the self-reference `legal_documents
   ||--o{ legal_documents : parent_of`.
4. `Next Steps` section updated.
5. CLAUDE.md §4 updated to reflect ADR-009 acceptance and the
   shrunken open-TODO list.
6. No changes to ADR-001 through ADR-008 invariants:
   - ADR-002 five-table list — unchanged.
   - ADR-003 chunks DDL FK columns — unchanged.
   - ADR-006 `doc_type` / `level` representation — unchanged.
   - ADR-007 `doc_type_code` — unchanged.
   - ADR-008 no-JSONB policy — strengthened (this column is a
     promotion, not a JSONB field).

## Revisit triggers

ADR-009 is revisited if any of the following hold:

- **First 시행규칙-bearing statute enters scope.** Decision needed:
  does the Rules' `parent_doc_id` point to the Act or to the Decree?
  In Korean legal practice 부령 제1조 typically delegates from both
  ("「○○법」 및 같은 법 시행령에서 위임된 사항…"), so a one-line
  heuristic is unlikely to suffice. Ratify in a follow-up ADR after
  examining the standardized 제1조 phrasing across multiple
  Rules-bearing statutes.
- **A Decree is observed without a matchable Act in the corpus.**
  E.g., a 대통령령 issued under an old law that has since been
  abolished. Action: extend the population rule to allow `NULL` as
  a documented terminal state, not an ingestion bug.
- **A Decree has multiple delegating Acts simultaneously.** Not
  observed in current corpus, but if surfaced, escalate to
  Option D (introduce `document_relations`).
- **TODO-2 (cross-statute citations) lands `document_relations`.**
  Verify ADR-009's `parent_doc_id` and TODO-2's edge-list table
  coexist cleanly with no role overlap.

## What is checked vs. what is still open

**Checked (this ADR):**

- API does not expose an explicit parent pointer (no
  `<상위법령>`, no `<위임법령>`, no `<모법ID>`).
- Title-pattern is the strongest derivation signal (`{Act_title}
  시행령`).
- 제1조 body text contains a reference to the parent Act in
  standard form.
- `자법타법여부` is not a parent-linkage indicator (empty in samples;
  semantically about amendment-side relationships).
- Cardinality of Act↔Decree is 1:N (tree), not M:N (graph).

**Still open (deferred):**

- Rules-parent assignment when both Act and Decree could delegate.
- `document_relations` shape for cross-statute citations (TODO-2).
- Whether to add a CHECK constraint after Phase-2 `doc_type`
  expansion stabilizes.
- Whether to add a verification-trigger ADR-006-style at first
  Decree ingestion (i.e., assert the title-match found exactly one
  Act).

## References

- `docs/legal-erd-draft.md` — TODO-10 specification
- `docs/decisions/ADR-002-identifier-strategy.md` — IDENTITY PK
  pattern that this FK references
- `docs/decisions/ADR-006-doc-type-and-level-enums.md` — `doc_type`
  values used in the population rule
- `docs/decisions/ADR-008-jsonb-on-statute-tables.md` — "promote
  when needed" policy that this ADR exercises
- `docs/api-samples/law-228817-중대재해처벌법.xml` — Act XML
- `docs/api-samples/law-277417-중대재해처벌법시행령.xml` — Decree
  XML; 제1조 evidence of standardized 위임 phrase
- `docs/api-samples/search-중대재해.xml` — confirms `자법타법여부`
  is empty for both documents
