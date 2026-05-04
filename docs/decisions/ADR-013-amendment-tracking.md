# ADR-013 — Amendment tracking: `is_head` and temporal effectiveness

- **Status**: Accepted
- **Date**: 2026-05-04
- **Context layer**: Statute (성문규범) ingestion pipeline —
  temporality and idempotency
- **Resolves**:
  - TODO-5 operational rule: whether `node_id` / `annex_id` /
    `form_id` are retained across amendments or version-scoped.
  - What `_skip_if_present()` should do when it sees a same-`mst`
    content-hash mismatch.
  - Replacement of the ambiguous `is_current` column with `is_head`.
  - Query semantics for head-version lookup vs legally effective
    version lookup.
- **Amends**:
  - **ADR-009 (Accepted)** — replace current Act lookup predicates that
    used `is_current = TRUE` with `is_head = TRUE` or
    `superseded_at IS NULL`.
  - **ADR-010 (Accepted)** — replace frozen `is_current BOOLEAN` columns
    on temporal source tables with `is_head BOOLEAN NOT NULL`.
- **Depends on / aligned with**:
  - **ADR-002 (Accepted)** — `mst` is the version-specific natural key;
    child tables use `(doc_id, natural_key)` UNIQUE constraints.
  - **ADR-011 (Accepted)** — raw XML retention makes old versions
    replayable.
  - **ADR-012 (Accepted)** — sub-조 `node_key` values are stable for
    re-ingest but not guaranteed stable across amendments that insert
    new 항/목 before existing siblings.
- **Out of scope (not decided here)**:
  1. Full legal-history query UI.
  2. Structural diffing between versions.
  3. Mapping a changed row in one version to its successor row in the next
     version when natural keys drift.
  4. Parent-version semantics for unchanged Decrees after an Act-only
     amendment. ADR-009's head lookup remains the Phase-1 rule; richer
     document-edge temporality can land as an additive relation later.
  5. Chunks refresh policy. This ADR only states source-row lifecycle.

## Context

The first amendment-tracking draft used `is_current` to represent the
"current version" of a legal document. That name is semantically
ambiguous once future-effective versions can be ingested:

- It can mean the version legally effective now.
- It can mean the latest ingested version.
- It can mean the version not yet superseded.

Those meanings diverge when a future-effective version exists.

Example:

- Version A is legally effective now.
- Version B has a future `effective_at` but has already been ingested.

In that state, A is the legally effective version, while B is the latest
ingested version. `is_current` cannot name both concepts correctly.

Legal effectiveness is already derivable:

```sql
effective_at <= :as_of
AND (superseded_at IS NULL OR superseded_at > :as_of)
```

Storing `is_current` as if it meant legal effectiveness would duplicate
derived state and create inconsistency risk. The ingestion pipeline still
needs a cheap way to find the latest ingested row in a `law_id` lineage,
but that is a different concept.

## Decision

Replace `is_current` with:

```sql
is_head BOOLEAN NOT NULL
```

A **head version** is the most recently ingested version within a given
`law_id` lineage.

It does **not** imply that the version is legally effective at the current
time.

Use **immutable version rows**. Each `legal_documents.mst` is a distinct
version. A new amendment with a new MST inserts a new `legal_documents`
row and a fresh set of child rows. The previous head version for the same
`law_id` is marked non-head. Primary keys (`doc_id`, `node_id`,
`annex_id`, `form_id`) are version-scoped and are **not retained across
amendments**.

Natural keys remain the cross-version alignment surface:

- `legal_documents.law_id` identifies the law lineage.
- `legal_documents.mst` identifies a specific version.
- `structure_nodes.node_key`, `annexes.annex_key`, and `forms.form_key`
  align rows across versions only when the source key remains stable.

## Conceptual model

| Concept | Meaning | Implementation |
|---------|---------|----------------|
| Head version | Latest ingested version in a `law_id` lineage | `is_head = TRUE` |
| Effective version | Legally valid at a given time | computed from `effective_at` / `superseded_at` |

`HEAD != CURRENT`.

`HEAD` is an ingestion concept. `CURRENT` is a temporal effectiveness
concept.

## Query semantics

### Head version lookup

```sql
WHERE law_id = :law_id
  AND is_head = TRUE
```

Equivalent when the supersession invariant holds:

```sql
WHERE law_id = :law_id
  AND superseded_at IS NULL
```

### Effective version at a given time

```sql
WHERE law_id = :law_id
  AND effective_at <= :as_of
  AND (superseded_at IS NULL OR superseded_at > :as_of)
```

This is the only accepted way to answer "which version is legally
effective at time T?"

## Same-MST behavior

Same `mst` + same `content_hash` remains a no-op.

Same `mst` + different `content_hash` remains a hard error. Do not
supersede. Do not update in place. `mst` is the API's version-specific
identity; if the same `mst` produces different bytes, the problem is API
drift, local file corruption, or hash computation drift. Treating that as
an amendment would collapse two incompatible payloads into one version key.

## New-MST ingestion rule

When ingesting a document whose `mst` is absent:

1. Compute `incoming_effective_at` from `effective_date` at
   `00:00:00 Asia/Seoul`.
2. Find existing head rows in `legal_documents` with the same `law_id`.
3. Before inserting the incoming head row, mark those rows:
   - `is_head = FALSE`
   - `superseded_at = incoming_effective_at`
   - `updated_at = NOW()`
4. Insert the incoming `legal_documents` row with:
   - `effective_at = incoming_effective_at`
   - `superseded_at = NULL`
   - `is_head = TRUE`
5. Insert parsed child rows with the same `effective_at`,
   `superseded_at = NULL`, and `is_head = TRUE` where the child table has
   those columns.
6. Mark old temporal child rows under superseded `doc_id` values:
   - `structure_nodes`
   - `annexes`
   - `forms`

`supplementary_provisions` has no temporality columns in the frozen schema.
Those rows are version-scoped through `doc_id`; they are not updated during
supersession.

All steps for one document run in one transaction. If child insertion fails,
the supersession update rolls back with the insert, leaving the old head
version intact.

## Parent lookup interaction

Parent lookup uses the head-row rule:

```sql
SELECT doc_id
FROM legal_documents
WHERE title = :candidate_act_title
  AND doc_type = '법률'
  AND is_head = TRUE
```

The equivalent `superseded_at IS NULL` predicate is acceptable when the
query wants the latest ingested row independent of the flag column.

Phase ordering remains Act -> Decree -> Rules. If a new Act and matching
new Decree are ingested in one run, the Act phase supersedes the old Act
first; the Decree phase then links to the new head Act.

If an Act changes but a Decree does not get a new MST in the same run, the
existing Decree row is not cloned or re-parented. That is a deliberate
Phase-1 boundary: unchanged documents remain their own head version until
the API provides a new version row or a later document-edge temporality
model is introduced.

## Indexing strategy

Head lookup:

```sql
CREATE INDEX idx_legal_documents_head
ON legal_documents (law_id)
WHERE is_head = TRUE;
```

Alternative equivalent lookup:

```sql
CREATE INDEX idx_legal_documents_unsuperseded
ON legal_documents (law_id)
WHERE superseded_at IS NULL;
```

Temporal query support:

```sql
CREATE INDEX idx_legal_documents_temporal
ON legal_documents (law_id, effective_at, superseded_at);
```

Future optimization, if temporal queries become hot:

- PostgreSQL `tstzrange`
- GiST index for interval queries

## Options considered

| Option | Verdict |
|--------|---------|
| A. Immutable version rows with `is_head`; legal effectiveness computed from time columns | **accepted** — separates ingestion latest from legal effectiveness |
| B. Keep `is_current` for latest ingested version | rejected — name is ambiguous in the presence of future-effective versions |
| C. Store legal effectiveness in `is_current` | rejected — derivable state; creates inconsistency risk |
| D. Update rows in place and retain `node_id` / `annex_id` across amendments | rejected — loses history and requires reliable cross-version matching when natural keys drift |
| E. Same-MST hash mismatch triggers supersession | rejected — same MST is one version identity; mismatch is data-integrity failure, not amendment evidence |

## Consequences

- Clear distinction between latest ingested version and legally effective
  version.
- `node_id`, `annex_id`, and `form_id` are stable within one database
  version row, not across amendments.
- Future chunks that reference old source PKs remain historically valid,
  but current retrieval must index or filter effective source rows by time
  or head source rows by ingestion lineage, depending on the use case.
- The current code's `ContentMismatchError` remains correct for same-MST
  mismatch. Implementation work is the new-MST supersession branch.
- Existing `is_current` usages must be migrated to `is_head` or temporal
  predicates.

## Implementation notes

- Replace `is_current` columns with `is_head BOOLEAN NOT NULL` on:
  - `legal_documents`
  - `structure_nodes`
  - `annexes`
  - `forms`
- Rename current-row indexes and predicates:
  - `ux_legal_documents_current_act_title` -> head-title equivalent.
  - `WHERE is_current = TRUE` -> `WHERE is_head = TRUE` for head lookup.
  - legal effectiveness queries must use `effective_at` /
    `superseded_at`.
- Rename `_skip_if_present()` or split it into an existence check that can
  distinguish:
  - same MST + same hash -> skip
  - same MST + different hash -> raise
  - absent MST + existing head `law_id` -> supersede then insert
  - absent MST + no head `law_id` -> insert
- Set `effective_at` explicitly on new `legal_documents`,
  `structure_nodes`, `annexes`, and `forms` rows instead of relying only on
  table defaults.
- Supersede old child rows by `doc_id IN (:superseded_doc_ids)`.
- Keep the operation inside the existing phase transaction.

## Test plan

- Same MST + same hash skips without duplicating parent or child rows.
- Same MST + different hash raises `ContentMismatchError`.
- Future-effective version fixture:
  - previous version remains effective under the temporal query
  - future version is the head row
  - no query relies on `is_head` to mean legally effective now
- New MST with same `law_id`:
  - old `legal_documents.is_head = FALSE`
  - old `legal_documents.superseded_at = incoming_effective_at`
  - new `legal_documents.is_head = TRUE`
  - new `legal_documents.effective_at = incoming_effective_at`
  - old temporal child rows are marked non-head
  - new child rows are inserted with fresh PKs
- Head Act title lookup remains unique after Act supersession.
- Act-before-Decree phase ordering links a new Decree to the new head Act.
- Transaction rollback test: force child insertion failure and verify the
  old head version remains head.

## References

- `docs/legal-erd-draft.md` — TODO-5 and temporality columns
- `docs/decisions/ADR-002-identifier-strategy.md`
- `docs/decisions/ADR-009-act-decree-linkage.md`
- `docs/decisions/ADR-010-phase-1-ddl-freeze.md`
- `docs/decisions/ADR-011-raw-api-xml-retention.md`
- `docs/decisions/ADR-012-structure-nodes-keying-and-sort.md`
- `src/ingest/populate.py` — current `_skip_if_present()` /
  `ContentMismatchError` behavior
