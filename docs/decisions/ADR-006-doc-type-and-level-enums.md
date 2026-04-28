# ADR-006 — `doc_type` and `level` enum values + representation pattern

- **Status**: Accepted
- **Date**: 2026-04-28
- **Context layer**: Statute (성문규범) ERD
- **Resolves**: TODO-6 in `docs/legal-erd-draft.md`
- **Depends on / aligned with**: TODO-3 (Phase-1 ERD scope, just resolved
  via doc-cleanup) — its "design for additive extension" guidance is
  observed but not load-bearing here; the recommendation rests on its
  own merits. ADR-002 (BIGINT IDENTITY + natural-key UNIQUE — `doc_type`
  is *not* a natural key, so the constraint pattern is independent).
- **Out of scope (not decided here)**:
  1. Whether `level` should be a column at all vs. derived from a
     `parent_id` traversal. The ERD draft's current shape has `level`
     as a column; this ADR decides the value space and representation
     for that column without reopening the column-existence question.
  2. Display-side localization (showing "Article" vs "조" vs "5"). A
     UI / API-response concern, not a schema concern.
  3. Future `doc_type` values for administrative regulations (행정규칙)
     or local ordinances (자치법규). Out of Phase-1 scope per TODO-3.

## Context

`structure_nodes.level` and `legal_documents.doc_type` are typed
columns whose value space the ERD draft sketched without finalizing.
TODO-6 carries three coupled sub-decisions:

1. **`doc_type` value set** — which formal Korean statute-type names.
2. **`level` value set** — integer 1–8 vs text labels (`'article'`,
   `'paragraph'`, …).
3. **Representation pattern** for both — PG ENUM type vs CHECK
   constraint on TEXT/INT vs reference table.

These matter because:

- The columns are queried and filtered constantly. `WHERE level <= 5`
  ("everything article-or-bigger") and `WHERE doc_type = '법률'` are
  baseline patterns for any retrieval-side query that respects the
  statute hierarchy.
- The current ERD draft labels (`doc_type "법률 | 시행령 | 시행규칙 | TODO-6"`)
  do **not match the API's actual returned values** (`법률`,
  `대통령령`). The ERD uses informal role names; the API returns
  formal type names. This ADR is the place to correct that.
- Postgres ENUM rigidity vs CHECK-on-TEXT flexibility is a recurring
  Postgres-design discussion; getting it wrong here means a non-
  trivial migration when Phase-2 expands.

## Empirical basis (verified 2026-04-28)

| Question | Finding | Source |
|----------|---------|--------|
| What does the API return for the Act's type? | `<법종구분 법종구분코드="A0002">법률</법종구분>` (lawService.do) and `<법령구분명>법률</법령구분명>` (lawSearch.do). Both APIs return the same formal value. | Act XML line 8; search XML inline |
| What does the API return for the Decree's type? | `<법종구분 법종구분코드="A0007">대통령령</법종구분>` and `<법령구분명>대통령령</법령구분명>`. **Not** 시행령 — that is informal/role-based usage; the formal type is 대통령령. | Decree XML line 8; search XML inline |
| Are 총리령 and 부령 also distinct formal types in this taxonomy? | Yes — they are the formal types corresponding to informal "시행규칙." 총리령 is issued by the Prime Minister; 부령 by a minister. Korean statute hierarchy treats them as distinct. (Inferred from the 법종구분 code structure A0002/A0007 + standard Korean legal taxonomy; not directly observed for this statute since 중대재해처벌법 has no 시행규칙 — confirmed by TODO-3.) | Inference from observed code pattern + standard legal taxonomy |
| Which `level` values does this statute actually use? | 2 (장), 5 (조), 6 (항), 7 (호), 8 (목). No 편(1), 절(3), 관(4) appear in 중대재해처벌법's structure. | Act XML — `<항>` at line 89, `<호>` at line 90, `<목>` at line 99; `조문여부` discriminates 전문 (heading) from 조문 (article) |
| Are the level positions stable across statutes? | Yes — Korean legal level hierarchy 편→장→절→관→조→항→호→목 is taxonomically closed and historically stable. New levels are not added between existing ones. | Standard legal taxonomy |
| Does the API expose the `법종구분코드` (e.g., `A0002`) separately from the value? | Yes — the code is a separate attribute on the same element, retrievable independently. | Act XML line 8 |

## Decision

### Sub-decision 1: `doc_type` value set

Phase-1 statute-family closed set:

- `법률` (Act)
- `대통령령` (Presidential Decree — issued by the President; what is
  informally called 시행령)
- `총리령` (Prime Minister Decree — what is informally called 시행규칙
  when issued by the PM's office)
- `부령` (Ministerial Decree — what is informally called 시행규칙 when
  issued by a minister)

Not included in Phase 1: `행정규칙`, `자치법규` (out of scope per
TODO-3).

### Sub-decision 2: `level` value set

Integer 1–8, mapped to the canonical Korean hierarchy:

| Level | Korean | Role |
|-------|--------|------|
| 1 | 편 | Part |
| 2 | 장 | Chapter |
| 3 | 절 | Section |
| 4 | 관 | Division |
| 5 | 조 | Article |
| 6 | 항 | Paragraph |
| 7 | 호 | Subparagraph |
| 8 | 목 | Item |

For 중대재해처벌법 specifically, only {2, 5, 6, 7, 8} are populated.
The full 1–8 range is committed because the level taxonomy is
statute-family-closed, not statute-specific.

### Sub-decision 3: Representation pattern

- `doc_type`: **`TEXT` with `CHECK (doc_type IN ('법률', '대통령령',
  '총리령', '부령'))`**.
- `level`: **`SMALLINT` with `CHECK (level BETWEEN 1 AND 8)`**.

No `CREATE TYPE … AS ENUM`. No reference tables.

```sql
ALTER TABLE legal_documents
  ADD CONSTRAINT chk_legal_documents_doc_type
  CHECK (doc_type IN ('법률', '대통령령', '총리령', '부령'));

ALTER TABLE structure_nodes
  ADD CONSTRAINT chk_structure_nodes_level
  CHECK (level BETWEEN 1 AND 8);
```

**DDL convention** (acceptance refinement, 2026-04-28): the named
constraints land **inline on `CREATE TABLE`**, not as follow-up
`ALTER TABLE` statements. The `ALTER TABLE` form above illustrates
constraint shape only; the canonical form lives in the migration
that creates the table.

## Options considered

### For `doc_type` representation

| Option | Verdict |
|--------|---------|
| A. PG ENUM type (`CREATE TYPE doc_type AS ENUM (...)`) | rejected — `ALTER TYPE … ADD VALUE` is supported but cannot run inside a transaction (Postgres ≥ 12 caveat); reordering is impossible without drop-and-recreate; some ORMs handle ENUMs awkwardly. The benefits (4-byte storage, type-safety) do not offset the schema-evolution friction for a value set that may grow in Phase 2. |
| B. **`TEXT` + `CHECK` constraint** | **accepted** |
| C. Reference table (`doc_types(code TEXT PK, label TEXT)` + FK on `legal_documents`) | rejected — overkill for a closed taxonomy of ~4 values with no per-type metadata that earns the join. Adopt later if Phase 2+ adds attributes to types (e.g., display label, hierarchical parent type). |
| D. No constraint at all (just `TEXT`, application enforces) | rejected — defeats the DB-enforced-integrity precedent in ADR-002/003. The ingestion phase is when constraint-based bug-catching is most valuable. |

### For `level` representation

| Option | Verdict |
|--------|---------|
| A. **`SMALLINT` + `CHECK (BETWEEN 1 AND 8)`** | **accepted** |
| B. `TEXT` with values like `'part'`, `'chapter'`, … | rejected — gives up the "filter by depth" / "ORDER BY level" / "WHERE level <= 5" query patterns that are baseline for tree-walks. Saves nothing — application code still maps the value to a display name. |
| C. PG ENUM ordered (`CREATE TYPE level AS ENUM ('편', '장', …)`) | rejected — Korean strings as ENUM values introduce encoding/quoting friction in DDL; the integer ordering is what we actually want for queries; no reordering ever needed since the taxonomy is closed. |
| D. `INT` (4 bytes) instead of `SMALLINT` (2 bytes) | rejected — 8-value range fits trivially in 2 bytes; storage difference is real but small. Either works. SMALLINT is the textbook choice for a known-tiny range. |

### For `doc_type` value set: store the Korean string vs the API code (`A0002`)?

| Option | Verdict |
|--------|---------|
| **Korean string** (`'법률'`, `'대통령령'`, …) | **accepted** — human-readable in queries, matches what both `lawService.do` and `lawSearch.do` return as the *value* element, ORM-friendly. |
| API code (`'A0002'`, `'A0007'`, …) | rejected — opaque in queries, requires a join or a lookup table to resolve, and the code-to-value mapping is itself a stable Korean-legal-taxonomy mapping that does not earn its abstraction. The code remains accessible via the source XML if ever needed (ingestion can stash it in a future `doc_type_code` column or a JSONB metadata sidecar — out of scope here). |

## Why these picks

1. **`TEXT` + `CHECK` is the right elasticity profile for a small,
   closed-but-extensible taxonomy.** Adding `'행정규칙'` or
   `'자치법규'` in Phase 2 is a one-line migration: drop the CHECK,
   add a wider one. PG ENUM imposes the same migration cost plus
   transaction caveats and ORM friction; reference tables impose a
   join cost forever to support a feature (per-type metadata) we
   don't need.

2. **Integer levels keep tree-walk queries trivial.** Phase-1 query
   patterns include "find all articles" (`WHERE level = 5`), "find
   all section headers" (`WHERE level <= 4`), and `ORDER BY level`
   for hierarchical traversal. Text labels lose all of this. The
   readability argument cuts the other way — a database column is
   read by SQL, not by humans, and SQL filters on integers more
   cleanly than on strings.

3. **Use the formal Korean type names, not the informal role names.**
   The ERD draft's current `doc_type "법률 | 시행령 | 시행규칙"` list
   does not match what the API returns. 시행령 is *role* language
   ("which Act does this implement"); 대통령령 is *type* language
   ("how was this issued"). The API returns the type. Storing
   anything other than the type forces an ingestion-time translation
   that breaks the natural-value pattern from ADR-002. Treat the
   formal Korean string as canonical.

4. **DB-enforced constraints in Phase 1 catch ingestion bugs early
   (consistent with ADR-002, ADR-003).** Same reasoning — the
   ingestion script is where constraint-based bug-catching is most
   valuable. Both `doc_type` and `level` get CHECK constraints, not
   "trust the application."

5. **Closed taxonomy reasoning matches Korean legal reality.** The
   level hierarchy 편→장→절→관→조→항→호→목 is taxonomically
   closed — no level has been added between existing ones in the
   modern statute era. The statute-family types {법률, 대통령령,
   총리령, 부령} are likewise closed at the type-level (what
   *expands* in Phase 2 is the broader "수범자" or
   "rule-of-law-class" set: 행정규칙, 자치법규 — those are siblings
   of the statute family, not new members of it). So the design
   risk of "we'll need to insert a new level between 4 and 5" is
   essentially nil.

## Consequences

- **ERD draft `legal_documents.doc_type` field comment must be
  corrected** from `"법률 | 시행령 | 시행규칙 | TODO-6"` to
  `"법률 | 대통령령 | 총리령 | 부령"`. The current label uses
  informal role names; the API returns formal type names. To be
  applied on acceptance.
- **ERD draft `structure_nodes.level` field comment is consistent**
  with this decision (already says `"1=part 2=chapter 3=section
  4=division 5=article 6=paragraph 7=subparagraph 8=item TODO-6"`).
  Resolves the TODO-6 marker; minor wording polish on acceptance.
- **DDL pattern**: both constraints are named (e.g.,
  `chk_legal_documents_doc_type`) so future migrations can drop
  them by name without ambiguity. Implicit-named constraints are
  a maintenance hazard.
- **The API's `법종구분코드` (e.g., `A0002`) is captured at
  ingestion time but does not currently land on the schema.** If
  Phase 2+ ever needs code-stable type tracking (e.g., the API
  changes the Korean string but keeps the code), adding a
  `doc_type_code TEXT` column on `legal_documents` is a non-
  breaking migration. Out of scope for this ADR.

## Trade-offs accepted

- **CHECK-vs-ENUM is mostly cosmetic at ~4 values; we are
  picking the more flexible side knowingly**. If 4 values stays
  4 values forever, ENUM would have been fine. The premium we pay
  for CHECK is one row in `pg_constraint` instead of an entry in
  `pg_type`. The premium we'd pay for ENUM if we chose it and then
  had to evolve it includes the `ALTER TYPE` non-transactional
  caveat and ORM-handling quirks. CHECK wins on expected value.
- **`level` as `SMALLINT` is unambiguously good**, but readers used
  to text labels may need a one-time mental mapping. Mitigated by
  putting the mapping table in this ADR and on the `structure_nodes`
  field comment.
- **Storing Korean strings as the canonical `doc_type` couples the
  schema to the API's specific value strings.** If 법제처 ever
  changes "법률" to "법령(법률)", a migration is needed. Probability:
  near zero; these are statutorily-defined terms.

## Verification once accepted

1. Confirm the ERD draft `doc_type` field comment is updated to the
   formal type names.
2. Confirm both CHECK constraints land in the migration alongside
   the table CREATEs (not as an afterthought ALTER), with explicit
   names per the "Consequences" note above.
3. A quick ingestion-side sanity check: parsing `<법종구분>` element
   text yields exactly one of {법률, 대통령령, 총리령, 부령} for
   any in-scope law. If a sample ever yields something else
   (e.g., a future ingestion of 자치법규), the CHECK rejects the
   row with a clear error — that is the early-bug-catching value.

   **Inferred-value verification trigger** (acceptance refinement,
   2026-04-28): the first ingestion of any statute that carries a
   시행규칙 must verify that `<법종구분>` resolves to exactly
   `'총리령'` or `'부령'` — **not** a ministry-prefixed variant such
   as `'행정안전부령'`. If the observed value diverges from the
   inferred set, the CHECK value set in this ADR is revisited
   (likely toward broadening the set or capturing the ministry
   prefix as a separate column).

## What is checked vs. what is still open

**Checked (this ADR):**

- Both API endpoints (lawService.do, lawSearch.do) return the formal
  Korean type names (법률, 대통령령) for the two Phase-1 documents.
- The `법종구분코드` ↔ value mapping is stable within the API
  contract (single attribute + element pair on each request).
- The level hierarchy 편→장→절→관→조→항→호→목 is canonical Korean
  legal taxonomy.

**Still open (deferred):**

- Whether 총리령 and 부령 ever appear in the API response shape this
  ADR assumes. Not directly observed; inferred from taxonomy. First
  ingestion of a statute that has 시행규칙 will verify or trigger a
  small revision.
- Whether to capture `법종구분코드` on the schema. Currently no — see
  "Consequences" final bullet. Revisit if API-version-stability
  becomes a real concern.

## References

- `docs/legal-erd-draft.md` — TODO-6 at lines 369–400; `legal_documents`
  / `structure_nodes` field comments to update on acceptance
- `docs/decisions/ADR-002-identifier-strategy.md` — DB-enforced
  constraint precedent that this ADR extends to `doc_type` / `level`
- `docs/decisions/ADR-003-chunks-fk-shape.md` — "DB-enforced integrity
  catches ingestion bugs early" reasoning that this ADR reuses
- `docs/api-samples/law-228817-중대재해처벌법.xml` line 8 —
  `법종구분코드="A0002"` `법률`
- `docs/api-samples/law-277417-중대재해처벌법시행령.xml` line 8 —
  `법종구분코드="A0007"` `대통령령`
- `docs/api-samples/search-중대재해.xml` — `<법령구분명>` evidence
  that lawSearch.do uses the same formal type names
