# ADR-020 — Effective-date slices are part of statute raw XML identity

- **Status**: Proposed
- **Date**: 2026-05-06
- **Context layer**: Statute raw retention, amendment tracking, OSH ingestion
- **Amends**:
  - **ADR-011** — `data/raw/{law_id}/{mst}.xml` is not sufficient for
    effective-date-specific `lawService.do?target=eflaw` responses.
  - **ADR-013** — `mst` alone is not the local document-version identity
    when one promulgated law version has multiple staged effective dates.
  - **ADR-019** — OSH ingestion is blocked until this identity rule is
    accepted.
- **Depends on / aligned with**:
  - **ADR-015** — any DDL change ships as an ordered SQL migration.
  - **ADR-019** — Phase 1 retains both legally effective and
    head/future-effective OSH slices.
- **Out of scope**:
  1. Full legal-history UI.
  2. Structural diffing between effective slices.
  3. Chunk refresh policy for slice changes.
  4. Retaining every historical OSH slice before the Phase-1 target set is
     explicitly enumerated.

## Context

ADR-011 assumed one retained XML file per `(law_id, mst)`:

```text
data/raw/{law_id}/{mst}.xml
```

ADR-013 then treated `legal_documents.mst` as the version-specific natural
key. That was defensible for SAPA because the retained Phase-1 samples did
not expose staged effective-date variants under the same MST.

ADR-019 deliberately expanded Phase 1 to OSH and required API discovery
before code changes. That discovery found the assumption is false for OSH.
`lawSearch.do?target=eflaw` returns repeated `mst` values with different
`시행일자`, and `lawService.do?target=eflaw&MST=...&efYd=...` returns
different XML bytes for those rows.

Measured examples from 2026-05-06 discovery:

| Law | MST | efYd values checked | Distinct XML hashes |
| --- | --- | --- | --- |
| `산업안전보건법` | `283449` | `20260601`, `20260801`, `20270101` | 3 |
| `산업안전보건법` | `206708` | `20210101`, `20210116` | 2 |
| `산업안전보건법 시행령` | `263363` | `20240701`, `20250101`, `20260626` | 3 |
| `산업안전보건법 시행규칙` | `263749` | `20240701`, `20250101`, `20260626` | 3 |
| `산업안전보건법 시행규칙` | `271485` | `20250601`, `20260101` | 2 |

Additional discovery result:

- `lawSearch.do?target=law` reports OSH Rule `MST=271485` with
  `시행일자=20260101`.
- `lawService.do?target=law&MST=271485` returns XML whose
  `<시행일자>` is `20250601`.
- Adding `efYd=20260101` to `target=law` does not change the returned XML.
- `target=eflaw` is therefore the endpoint that preserves staged
  effective-date identity.

The existing path would collapse these payloads into one file. The current
database uniqueness rule would also collapse them into one
`legal_documents` row.

## Decision

Treat an effective-law source row as a **document slice**, not just a
document version.

The local identity for retained `target=eflaw` statute XML is:

```text
(target, law_id, mst, efYd)
```

The local identity for ingested statute source rows is:

```text
(law_id, mst, effective_date)
```

`mst` remains an upstream promulgation-version identifier, but it is not
alone sufficient for local source-row identity when staged enforcement
exists.

### Raw retention path

Keep the existing ADR-011 path for already retained `target=law` responses:

```text
data/raw/{law_id}/{mst}.xml
```

Add a separate path for effective-date-specific responses:

```text
data/raw/eflaw/{law_id}/{mst}/{efYd}.xml
```

Rules:

1. Fetch every effective-date-specific row through
   `lawService.do?target=eflaw&MST={mst}&efYd={YYYYMMDD}&type=XML`.
2. Do not use `target=law` to populate effective-date-specific rows when
   `lawSearch.do?target=eflaw` supplied the row.
3. `legal_documents.content_hash` remains the SHA-256 of the exact retained
   XML file.
4. `legal_documents.source_url` must record the non-OC endpoint identity,
   including `target=eflaw`, `MST`, and `efYd` for effective-law rows.

### Database identity

Replace the current `UNIQUE (mst)` invariant with:

```sql
UNIQUE (law_id, mst, effective_date)
```

Same `(law_id, mst, effective_date)` plus different `content_hash` remains
a hard integrity error.

Same `(law_id, mst)` plus different `effective_date` is valid and inserts a
separate immutable `legal_documents` row with its own child rows.

Temporal supersession must be computed over ordered effective slices within
a `law_id` lineage:

```text
slice N superseded_at = slice N+1 effective_at
latest retained slice superseded_at = NULL
latest retained slice is_head = TRUE
all older slices is_head = FALSE
```

This preserves ADR-013's distinction:

- `is_head` = latest retained slice in the lineage
- legal effectiveness at time T = temporal predicate over
  `effective_at` / `superseded_at`

### Parent lookup

ADR-009's parent lookup by head Act remains acceptable for Phase 1 only as
an ingestion ordering shortcut.

For retrieval/evaluation, parent-child legal coherence must be determined
by the same as-of date filter, not by `is_head`.

## Options considered

| Option | Verdict |
| --- | --- |
| A. Keep `data/raw/{law_id}/{mst}.xml` and `UNIQUE(mst)` | rejected — empirically collapses distinct OSH XML payloads |
| B. Store `target=eflaw` as `data/raw/{law_id}/{mst}-{efYd}.xml` | rejected — workable but mixes endpoint-specific identity into the old flat directory |
| C. Store `target=eflaw` under `data/raw/eflaw/{law_id}/{mst}/{efYd}.xml` and change DB identity to `(law_id, mst, effective_date)` | proposed — explicit endpoint boundary and no collision with existing SAPA files |
| D. Store raw XML in the database to avoid path design | rejected — reopens ADR-011's rejected option without solving DB row identity |
| E. Ingest only one effective date per MST | rejected — violates ADR-019 and loses staged-enforcement semantics |

## Consequences

- OSH ingestion requires a migration before source rows can be written.
- `scripts/fetch_law_samples.sh` can remain SAPA-compatible, but OSH fetch
  code must support `target=eflaw` and the new raw path.
- `src/ingest/parse.py::discover()` must learn the `eflaw` raw path or an
  explicit manifest must feed parser paths.
- `ContentMismatchError` must move from "same MST" to
  "same `(law_id, mst, effective_date)`".
- `legal_documents.is_head` remains a single latest retained slice per
  law lineage, so the existing head Act title uniqueness concept survives
  after its supporting constraint is migrated.
- Current-law retrieval for ADR-019 must filter by `effective_at` /
  `superseded_at` as of `2026-05-06`, not by `is_head`.

## Acceptance criteria

- Migration replaces `uk_legal_documents_mst` with a uniqueness rule over
  `(law_id, mst, effective_date)`.
- OSH effective-law XML is retained at
  `data/raw/eflaw/{law_id}/{mst}/{efYd}.xml`.
- Re-fetching the same `(law_id, mst, effective_date)` with a different
  hash fails fast.
- Same `(law_id, mst)` with different `effective_date` inserts separate
  immutable source rows.
- Parser/populator source URLs for effective-law rows include
  `target=eflaw` and `efYd`, without OC.
- Current-law retrieval/eval can select the as-of `2026-05-06` slice
  without relying on `is_head`.
