# ADR-020 — `eflaw` is the canonical statute XML source

- **Status**: Accepted
- **Date**: 2026-05-06
- **Context layer**: Statute raw retention, amendment tracking, OSH ingestion
- **Amends**:
  - **ADR-011** — canonical statute XML retention moves from
    `data/raw/{law_id}/{mst}.xml` to an effective-date-specific `eflaw`
    path for Phase 1 statute ingestion.
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
  2. Structural diffing between effective-date slices.
  3. Chunk refresh policy for slice changes.
  4. Retaining every historical OSH slice before the Phase-1 target set is
     explicitly enumerated.

## Context

The original Phase-1 raw-retention model assumed one statute source row
could be identified by:

```text
(law_id, mst)
```

and retained as:

```text
data/raw/{law_id}/{mst}.xml
```

ADR-013 then treated `legal_documents.mst` as the version-specific natural
key. That was defensible for SAPA because the retained Phase-1 samples did
not expose staged effective-date variants under the same MST.

ADR-019 expanded Phase 1 to OSH and required API discovery before code
changes. That discovery proved the assumption is false for statutes with
staged effective dates.

For OSH, the same `mst` can have multiple effective dates, and each
effective date can return different XML through:

```text
lawService.do?target=eflaw&MST={mst}&efYd={YYYYMMDD}&type=XML
```

These payloads are not different laws. They are different
**effective-date slices** of the same law:

```text
the statute XML as applicable from a specific effective date
```

Example:

```text
산업안전보건법, MST=283449

efYd=20260601 -> XML effective on 2026-06-01
efYd=20260801 -> XML effective on 2026-08-01
efYd=20270101 -> XML effective on 2027-01-01
```

Measured examples from 2026-05-06 discovery:

| Law | MST | efYd values checked | Distinct XML hashes |
| --- | --- | --- | --- |
| `산업안전보건법` | `283449` | `20260601`, `20260801`, `20270101` | 3 |
| `산업안전보건법` | `206708` | `20210101`, `20210116` | 2 |
| `산업안전보건법 시행령` | `263363` | `20240701`, `20250101`, `20260626` | 3 |
| `산업안전보건법 시행규칙` | `263749` | `20240701`, `20250101`, `20260626` | 3 |
| `산업안전보건법 시행규칙` | `271485` | `20250601`, `20260101` | 2 |

## `law` and `eflaw` are not equivalent

`target=law` is closer to a promulgation-version or representative
current-law response.

`target=eflaw` is the effective-date-specific response and supports
fetching XML by `efYd`.

The discovery result showed that `target=law` may not preserve
effective-date-specific identity:

- `lawSearch.do?target=law` reported OSH Rule `MST=271485` with
  `시행일자=20260101`.
- `lawService.do?target=law&MST=271485` returned XML whose internal
  `<시행일자>` was `20250601`.
- Adding `efYd=20260101` to `target=law` did not change the returned XML.

Therefore, `target=law` cannot be trusted as the canonical source for
staged effective-date XML.

The endpoint that preserves staged effective-date identity is:

```text
target=eflaw
```

## Decision

For Phase 1 statute ingestion, use `target=eflaw` as the canonical source
for retained statute XML.

Do **not** retain `target=law` responses as parallel canonical raw
documents when `eflaw` rows are available.

The canonical retained XML identity for `eflaw` rows is:

```text
(target=eflaw, law_id, mst, efYd)
```

The canonical ingested document identity is:

```text
(law_id, mst, effective_date)
```

`target` is fixed to `eflaw` for canonical Phase-1 statute XML, so it does
not participate in the `legal_documents` uniqueness rule. It remains part
of raw-source provenance and must be recorded in `source_url`.

`mst` remains an upstream promulgation-version identifier, but it is not
alone sufficient for local source-row identity when staged enforcement
exists.

## Raw retention path

Fetch every canonical statute XML through:

```text
lawService.do?target=eflaw&MST={mst}&efYd={YYYYMMDD}&type=XML
```

Store it at:

```text
data/raw/eflaw/{law_id}/{mst}/{efYd}.xml
```

`{law_id}` means the law.go.kr `법령ID`, not the human law title. Use:

```text
data/raw/eflaw/001766/283449/20260601.xml
data/raw/eflaw/001766/283449/20260801.xml
data/raw/eflaw/001766/283449/20270101.xml
```

not:

```text
data/raw/eflaw/산업안전보건법/283449/20260601.xml
```

Rules:

1. `legal_documents.content_hash` is the SHA-256 of the exact XML bytes
   stored on disk.
2. `legal_documents.source_url` records the non-OC API identity,
   including `target=eflaw`, `MST`, and `efYd`.
3. Do not use `target=law` to populate canonical `legal_documents` rows
   when an `eflaw` slice exists.

## Role of `target=law`

`target=law` is auxiliary, not a parallel source of truth.

Acceptable uses:

1. Discovery.
2. Fallback for statutes that do not expose `eflaw` rows.
3. Debugging.
4. Empirical comparison.
5. Temporary legacy verification.

If fallback ingestion from `target=law` ever becomes necessary, handle it
as an explicit branch with separate provenance. Do not silently mix `law`
and `eflaw` rows inside one canonical identity model.

## Database identity

Replace the old uniqueness rule:

```sql
UNIQUE (mst)
```

with:

```sql
UNIQUE (law_id, mst, effective_date)
```

Valid:

```text
(law_id=001766, mst=283449, effective_date=2026-06-01)
(law_id=001766, mst=283449, effective_date=2026-08-01)
(law_id=001766, mst=283449, effective_date=2027-01-01)
```

Invalid:

```text
same (law_id, mst, effective_date)
but different content_hash
```

A hash mismatch for the same identity is a hard integrity error.

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

- `is_head` = latest retained slice in the law lineage
- legal effectiveness at time T = temporal predicate over
  `effective_at` / `superseded_at`

## Legacy data policy

Existing Phase-1 `target=law` raw XML under:

```text
data/raw/{law_id}/{mst}.xml
```

is legacy data.

Because the Phase-1 retained dataset is still small, migrate toward one
canonical convention:

```text
data/raw/eflaw/{law_id}/{mst}/{efYd}.xml
```

Existing `target=law` samples should be removed or replaced by equivalent
`eflaw` slices after the replacement fetch is verified.

Do not permanently support both:

```text
data/raw/{law_id}/{mst}.xml
data/raw/eflaw/{law_id}/{mst}/{efYd}.xml
```

as equal canonical stores.

## Retrieval implication

Current-law retrieval must not rely on `is_head`.

`is_head` only means:

```text
latest retained slice in the law lineage
```

It does not necessarily mean:

```text
legally effective at query time
```

For retrieval and evaluation, select the legally applicable slice using an
as-of date predicate:

```text
effective_at <= as_of_date
AND (superseded_at IS NULL OR superseded_at > as_of_date)
```

For ADR-019 Phase 1, current-law retrieval selects slices as of:

```text
2026-05-06
```

## Parent lookup

ADR-009's parent lookup by head Act remains acceptable for Phase 1 only as
an ingestion ordering shortcut.

For retrieval/evaluation, parent-child legal coherence must be determined
by the same as-of date filter, not by `is_head`.

## Options considered

| Option | Verdict |
| --- | --- |
| A. Keep `data/raw/{law_id}/{mst}.xml` and `UNIQUE(mst)` | rejected — empirically collapses distinct OSH XML payloads |
| B. Store both `law` and `eflaw` as equal canonical raw sources | rejected — creates competing truths for the same statute slice |
| C. Use `target=eflaw` as canonical, store `data/raw/eflaw/{law_id}/{mst}/{efYd}.xml`, and change DB identity to `(law_id, mst, effective_date)` | proposed — matches retrieval's as-of-date semantics |
| D. Store raw XML in the database to avoid path design | rejected — reopens ADR-011's rejected option without solving row identity |
| E. Ingest only one effective date per MST | rejected — violates ADR-019 and loses staged-enforcement semantics |
| F. Use `target=law` canonical and `eflaw` only for comparison | rejected — discovery shows `target=law` can return the wrong effective-date state |

## Consequences

- OSH ingestion requires a migration before source rows can be written.
- Fetch tooling must support `target=eflaw` and the new canonical raw path.
- `scripts/fetch_law_samples.sh` becomes legacy/SAPA-compatible tooling
  unless it is upgraded to `eflaw`.
- `src/ingest/parse.py::discover()` must learn the `eflaw` raw path or an
  explicit manifest must feed parser paths.
- `ContentMismatchError` must move from "same MST" to
  "same `(law_id, mst, effective_date)`".
- Current `data/raw/{law_id}/{mst}.xml` files are migration candidates, not
  a permanent second canonical store.
- Current-law retrieval for ADR-019 must filter by `effective_at` /
  `superseded_at` as of `2026-05-06`, not by `is_head`.

## Acceptance criteria

- Migration replaces `uk_legal_documents_mst` with a uniqueness rule over
  `(law_id, mst, effective_date)`.
- Canonical statute XML for Phase 1 is retained through `target=eflaw` at
  `data/raw/eflaw/{law_id}/{mst}/{efYd}.xml`.
- Re-fetching the same `(law_id, mst, effective_date)` with a different
  hash fails fast.
- Same `(law_id, mst)` with different `effective_date` inserts separate
  immutable source rows.
- Parser/populator source URLs for canonical rows include `target=eflaw`
  and `efYd`, without OC.
- Existing SAPA `target=law` retained XML is removed or replaced by
  verified equivalent `eflaw` slices before broad OSH ingestion proceeds.
- Current-law retrieval/eval can select the as-of `2026-05-06` slice
  without relying on `is_head`.
