# ADR-007 — Capture `법종구분코드` as `doc_type_code` sibling column on `legal_documents`

- **Status**: Accepted
- **Date**: 2026-04-28
- **Context layer**: Statute (성문규범) ERD
- **Resolves**: ADR-006 "Still open" #2 (whether to capture
  `법종구분코드` on the schema)
- **Depends on / aligned with**: ADR-002 (natural-key UNIQUE pattern
  treats API-stable identifiers as first-class columns — `mst`,
  `law_id`), ADR-006 (human-readable `doc_type` is canonical for
  semantic queries; this ADR adds the API-stable code alongside, not
  in place of)
- **Out of scope (not decided here)**:
  1. Whether to add a CHECK constraint over `doc_type_code` values.
     Capture-as-observed is the recommendation; constraint is
     deliberately omitted (see "Decision" rationale).
  2. Whether to capture similar API-issued codes for *other* columns
     (e.g., a code variant of `competent_authority_code` already
     exists on the ERD; cross-field code-capture policy is
     case-by-case, not generalized here).
  3. Whether `doc_type` could be *derived* from `doc_type_code` via
     a mapping (would require a reference table — rejected here on
     overkill grounds; both columns are captured directly).

## Context

The 법제처 OpenAPI returns the law-type element with **two** pieces of
information in one place:

```xml
<법종구분 법종구분코드="A0002">법률</법종구분>
<법종구분 법종구분코드="A0007">대통령령</법종구분>
```

ADR-006 chose the **element text** (`법률`, `대통령령`) as the
canonical `doc_type` value — human-readable, ORM-friendly, query-
clear. ADR-006 explicitly deferred the `법종구분코드` (`A0002`,
`A0007`) attribute as out-of-scope, leaving it as the second item in
its "Still open" list.

This ADR closes that.

The decision matters because:

- The code is **already on the parse path** — same XML element whose
  text becomes `doc_type`. Ignoring an attribute the parser already
  touches is a small but real form of data loss.
- Backfill is **asymmetrically expensive**. Capturing now is a
  one-line ingestion-side change. Recovering later requires either
  retaining raw API XML indefinitely (a storage / governance
  decision not currently committed) or re-fetching the corpus
  (depends on API rate limits and version stability).
- ADR-006 itself flagged a residual risk: "If 법제처 ever changes
  '법률' to '법령(법률)', a migration is needed." Capturing
  `doc_type_code` hedges that risk near-cost-free — the migration
  becomes "rebuild `doc_type` from `doc_type_code` via a new map"
  rather than "re-fetch the corpus."
- Source-of-truth identifiers are evaluation infrastructure. A
  retrieval engine's eval harness needs traceability from
  query → result → source; API-issued stable identifiers are part
  of that chain.

## Empirical basis (verified 2026-04-28 — same evidence as ADR-006)

| Fact | Source |
|------|--------|
| `법종구분` element carries both text value and `법종구분코드` attribute on every observed law-detail response. | Act XML line 8: `<법종구분 법종구분코드="A0002">법률</법종구분>`; Decree XML line 8: `<법종구분 법종구분코드="A0007">대통령령</법종구분>` |
| Code value space follows an `A####` pattern in observed data. | Same source |
| `lawSearch.do` returns the value but **not** the code (different field shape: `<법령구분명>법률</법령구분명>`). | search XML inline |
| The code is therefore reachable only from `lawService.do`, not from `lawSearch.do`. | Above |

The single-endpoint reachability matters for the ingestion pipeline
shape but does not change the decision: the ingestion pipeline already
calls `lawService.do` per document (the `lawSearch.do` response is the
list-of-MSTs index, not the per-document parse target).

## Decision

Add a sibling column `doc_type_code TEXT NULL` on `legal_documents`.
No CHECK constraint. Populated at ingestion time from the
`법종구분코드` attribute of the `<법종구분>` element on
`lawService.do` responses.

```
legal_documents.doc_type       TEXT NOT NULL  CHECK (doc_type IN
                                              ('법률', '대통령령',
                                               '총리령', '부령'))
                                              -- ADR-006
legal_documents.doc_type_code  TEXT NULL      -- ADR-007 (this ADR)
                                              -- captured as observed
                                              -- from <법종구분 법종구분코드="…">
```

The two columns express different facets of the same fact:

- `doc_type` — **human-facing canonical** value. Queryable in
  natural Korean. Subject to a CHECK that enforces the closed
  Phase-1 type set.
- `doc_type_code` — **machine-facing stable identifier**. Captured
  for provenance and traceability. No CHECK; values land
  as-observed.

Neither replaces the other. Both are populated at ingestion.

## Options considered

| Option | Verdict |
|--------|---------|
| A. Don't capture (status quo from ADR-006) | rejected — see "vs. A" |
| **B. Sibling column on `legal_documents`** | **accepted** |
| C. JSONB metadata sidecar (`legal_documents.metadata` with `{"doc_type_code": "A0002"}`) | rejected — see "vs. C" |
| D. Reference table (`doc_types(code, name)` + FK from `legal_documents`) | rejected — see "vs. D" |
| E. Replace `doc_type` with `doc_type_code` (single column, code is canonical) | rejected — would undo ADR-006's human-readable canonical decision |

### Why B over A — the strongest competitor

A ("don't capture") is the steelman because the column adds storage
and conceptual surface for a value that today no query actually
needs. The arguments **for** A:

1. We don't query by code today. `doc_type` answers all current
   filtering needs.
2. YAGNI — adding a column "in case we need it later" is the kind
   of preemptive design the working agreements explicitly warn
   against.
3. The Korean strings are statutorily defined and unlikely to
   change.

The arguments **against** A (and why B wins):

1. **Asymmetric backfill cost.** Capturing now is one extra line at
   ingestion: read the attribute that's already on the parsed
   element. Recovering later requires either retained raw XML (no
   committed retention policy) or a re-fetch of the corpus
   (depends on uncommitted assumptions about API rate limits and
   version stability). The right time to capture provenance data
   is when it crosses the parser, not later.
2. **It is not "in case we need it later" — it is "we already have
   it in hand and would have to actively discard it."** YAGNI
   applies to building features, not to preserving observed source
   data. The parser already reads `<법종구분>` for `doc_type`;
   reading the `법종구분코드` attribute on the same element is
   passing-by data we'd otherwise drop.
3. **Hedges ADR-006's accepted residual risk.** ADR-006 traded off:
   "If 법제처 ever changes 법률 to 법령(법률), a migration is
   needed." With code captured, the migration shape is
   `UPDATE legal_documents SET doc_type = map(doc_type_code)` — a
   no-network operation. Without code captured, the migration
   requires source-of-truth re-derivation. The probability of the
   trigger is near zero, but the asymmetry of mitigation cost is
   real.
4. **Provenance is evaluation infrastructure.** This is a retrieval
   engine; its evaluation requires traceability from query through
   result back to source. API-issued stable identifiers are
   first-class provenance, not optional metadata. Treating them
   that way now avoids re-litigation when downstream tooling
   depends on it.

### Why B over C — JSONB metadata sidecar

C would stash the code in a `metadata` JSONB column:
`legal_documents.metadata = '{"doc_type_code": "A0002", ...}'`.
This is the natural shape for "API metadata we want to keep but not
promote to columns."

Why C loses:

1. **TODO-8 is unresolved.** The decision to add a JSONB metadata
   column on `legal_documents` is itself an open ERD decision. C
   couples ADR-007 to TODO-8, and TODO-8's options space is its
   own design discussion (whether to use JSONB at all, on which
   tables, with what schema). ADR-007 should not pre-decide TODO-8.
   *Update 2026-04-29*: TODO-8 is now resolved by ADR-008 — no
   JSONB on `legal_documents`. The C rejection holds for an
   additional reason: there is no JSONB target column for
   `doc_type_code` to land in.
2. **JSONB is the right shape for *unknown* metadata, not *known*
   single fields.** When you know exactly which field you want to
   capture and how it's queried, a typed column beats a JSON
   property on every dimension: query speed, type safety, ORM
   ergonomics, B-tree indexability, NULL semantics. The natural
   home for a known stable identifier is a column.
3. **C survives if TODO-8 lands JSONB.** Even if TODO-8 later
   adopts a `metadata` JSONB column, having `doc_type_code` as a
   sibling column does not block that — the JSONB can still hold
   *other* metadata. C and B are not mutually exclusive; the
   decision here is about the home of *this specific* field.

### Why B over D — reference table

D would be `doc_types(code TEXT PK, name TEXT NOT NULL)` + FK
`legal_documents.doc_type_code REFERENCES doc_types(code)`.

Why D loses:

1. **Overkill for a closed taxonomy with no per-row metadata.**
   Same argument ADR-006 used to reject reference tables for
   `doc_type` itself.
2. **Adds a JOIN forever** for queries that need both
   human-readable and code values. With B, both are columns on
   `legal_documents` — queryable in a single row.
3. **Wins only if per-type metadata grows** (display label,
   hierarchical parent type, taxonomy version, …). None of these
   are planned. Defer until they earn the join.

### Why B over E — replacing `doc_type`

E would make `doc_type_code` the only column, with the human
string derived in application code. Rejected outright — it
overturns ADR-006's accepted decision (human-readable canonical),
re-introduces ORM friction, and breaks the "natural Korean string
in WHERE clauses" pattern.

## Why nullable, no CHECK

The column's role is **provenance capture**, not **constraint
enforcement**. The constraint role is already played by `doc_type`'s
own CHECK. Implications:

- **Nullable** because the column should not block ingestion if the
  attribute is ever missing or malformed in a future API response.
  The `doc_type` CHECK still fires on the value side; we want the
  row to land with the partial data we did get, surfacing the
  attribute miss as auditable NULL rather than as a failed insert.
- **No CHECK** because we capture as observed. The current code
  pattern is `A####`, but binding that pattern as a constraint
  would force a migration if 법제처 ever issues a code outside the
  `A` prefix (e.g., a new `B` family for a new statute class). The
  cost of that constraint earning its keep is approximately zero
  today; the cost if violated is a migration. The lopsided cost
  argues against the constraint.

A future ADR can tighten this (NOT NULL, CHECK on prefix) once we
have empirical evidence that the API contract holds across enough
laws to justify the rigidity.

## Trade-offs accepted

- **Two columns expressing one fact.** Minor cognitive load;
  mitigated by clear column comments naming each role
  (human-canonical / machine-stable).
- **Storage cost.** ~5 bytes average per row plus NULL bitmap
  overhead. Negligible at any plausible Phase-1+ corpus size.
- **Schema couples to a specific API code system.** If 법제처
  re-issues codes under a different scheme (e.g., switches from
  the legacy gov-code system to a new namespace), both columns
  need migration. Probability is very low — this code system has
  been stable for decades — and the migration is local to
  `legal_documents`.
- **`doc_type_code` is reachable only via `lawService.do`.** The
  list endpoint (`lawSearch.do`) returns the value but not the
  code. The ingestion pipeline already calls `lawService.do`
  per-document, so this is not a new constraint, but it does mean
  any future "metadata-only" indexing pass that uses lawSearch
  alone will not have access to the code.

## Consequences

- ERD draft `legal_documents` block gains a new column row:
  `doc_type_code TEXT NULL` with a comment naming its role
  (machine-stable provenance counterpart to `doc_type`). To be
  applied on acceptance.
- The Mermaid diagram in the ERD draft gains the same column.
- ADR-006's "Still open" #2 closes (forward-pointer to be added on
  acceptance).
- Ingestion-side change: the parser, when reading `<법종구분>` for
  `doc_type`, additionally reads the `법종구분코드` attribute and
  populates `doc_type_code`. One line.
- Migration shape: when DDL is written, the column lands inline on
  `CREATE TABLE legal_documents` (same DDL convention as ADR-006).

## Verification once accepted

1. Confirm the new column appears in the ERD draft's
   `legal_documents` block and Mermaid diagram with the role-naming
   comment.
2. Confirm an ADR-006 forward-pointer marks "Still open" #2 closed.
3. First ingestion run populates both columns: `doc_type='법률'`
   with `doc_type_code='A0002'`, `doc_type='대통령령'` with
   `doc_type_code='A0007'`. Any divergence (NULL code with non-NULL
   type, or code without the `A####` shape) is surfaced as an
   ingestion-log warning, not as a CHECK failure.

## What is checked vs. what is still open

**Checked (this ADR):**

- `법종구분코드` attribute presence on `<법종구분>` for both
  Phase-1 documents (Act and Decree).
- `lawSearch.do` does not return the code (informs ingestion
  source-of-record decision).
- Asymmetry of capture cost (one line at ingestion) vs. backfill
  cost (retain XML or re-fetch).

**Still open (deferred):**

- Whether other API-stable codes warrant similar capture
  (`소관부처코드` is already captured; other code-bearing fields
  not yet inventoried). Case-by-case, not a generalized policy
  here.
- Whether `doc_type_code` ever earns a CHECK constraint or a
  reference-table FK. Revisit if Phase 2 brings ≥ 10 unique codes
  or per-type attributes.
- Whether the ingestion pipeline needs to handle the `lawSearch`-
  vs-`lawService` asymmetry differently (i.e., what to do if a
  metadata-only refresh path is ever introduced that uses
  lawSearch alone). Not a Phase-1 concern.

## References

- `docs/decisions/ADR-006-doc-type-and-level-enums.md` — upstream
  decision; "Still open" #2 closes on acceptance of this ADR
- `docs/decisions/ADR-002-identifier-strategy.md` — natural-key
  pattern that this ADR extends to a non-key API-stable identifier
- `docs/api-samples/law-228817-중대재해처벌법.xml` line 8 —
  evidence of `법종구분코드="A0002"` co-located with `법률` text
- `docs/api-samples/law-277417-중대재해처벌법시행령.xml` line 8 —
  evidence of `법종구분코드="A0007"` co-located with `대통령령` text
- `docs/api-samples/search-중대재해.xml` — confirms `lawSearch.do`
  omits the code
