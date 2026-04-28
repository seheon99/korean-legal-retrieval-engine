# ADR-008 — No JSONB `metadata` column on `legal_documents` or `structure_nodes`

- **Status**: Accepted
- **Date**: 2026-04-29
- **Context layer**: Statute (성문규범) ERD
- **Resolves**: TODO-8 in `docs/legal-erd-draft.md` (whether the
  statute tables should carry a JSONB `metadata` column for
  semi-structured data)
- **Depends on / aligned with**: ADR-007 (sibling-column-over-JSONB
  pattern for known stable identifiers; this ADR generalizes that
  reasoning to the table-level), ERD draft "Not stored (deliberate
  omissions)" list on `legal_documents` (this ADR ratifies that
  list as the ongoing policy rather than a temporary stance)
- **Out of scope (not decided here)**:
  1. `chunks.metadata` JSONB — already agreed in
     `docs/phase-1-progress.md` §5; orthogonal to TODO-8.
  2. `annexes.image_filenames` / `forms.image_filenames`
     representation (the "JSONB or text array" comment in the ERD).
     Small representational sub-decision; deferred to DDL time as a
     column-comment-only resolution unless it surfaces a real
     trade-off.
  3. TODO-5 amendment-tracking fields (`조문이동이전`, `조문이동이후`).
     These are amendment-temporality concerns, not catch-all metadata.
  4. Whether to formalize raw-API-XML retention as its own ADR.
     ADR-008 leans on the assumption that raw responses remain
     replay-available; this ADR flags the dependency without
     drafting a separate retention ADR. If retention is later
     formalized, a forward-pointer lands here.

## Context

`docs/legal-erd-draft.md` TODO-8 asks whether `legal_documents`
or `structure_nodes` should carry a JSONB `metadata` column for
semi-structured data — a catch-all for fields not worth promoting
to typed columns.

ADR-007 surfaced this question explicitly when it rejected its
option C ("stash `doc_type_code` in a JSONB sidecar") on the grounds
that "TODO-8 is unresolved" and "JSONB is the right shape for
*unknown* metadata, not *known* single fields." That left TODO-8 as
a live design slot. ADR-008 closes it.

The candidate audience for the JSONB column is a list of
법제처 OpenAPI fields the ERD currently does not promote to typed
columns:

- The ERD's "Not stored (deliberate omissions)" list:
  `연락부서`/`부서단위` (admin contacts), `개정문내용` (raw amendment
  text), `법령명_한자`.
- A handful of boolean-like flag fields on the document root that
  the ERD doesn't address explicitly: `한글법령여부`, `별표편집여부`,
  `공포법령여부`, `제명변경여부`, `언어`, `전화번호`,
  `공동부령정보`.
- Article-level amendment-tracking fields: `조문이동이전`,
  `조문이동이후` (TODO-5 territory).
- The root-element attribute `법령키` (e.g.,
  `0139932021012617907` = `법령ID` + `enacted_date` + `law_number`,
  derivable from existing columns).

The decision matters because:

- The shape of the answer is precedent-setting for the other category
  ERDs (사법판단 / 유권해석 / 학술자료 / 입법개정자료). The same
  question will arise on each. A clear "no JSONB" decision here, with
  the policy "promote when needed, omit deliberately, retain raw
  responses as the fallback," travels cleanly.
- JSONB-as-junk-drawer is a known anti-pattern that subverts the ERD's
  existing discipline ("every column has a confidence marker and a
  rationale"). Resolving TODO-8 in either direction is also resolving
  whether that discipline applies forward.

## Empirical basis (verified 2026-04-29 against existing API samples)

Files: `docs/api-samples/law-228817-중대재해처벌법.xml` (Act,
41 KB) and `law-277417-중대재해처벌법시행령.xml` (Decree, 95 KB).

After mapping every element back to the ERD — note that
`<항>`/`<호>`/`<목>` are *not* unmapped, they each become a
`structure_nodes` row at level 6/7/8 — the actual unmapped surface
falls into four buckets:

| Bucket | Fields | Disposition under ADR-008 |
|--------|--------|----------------------------|
| Constant boolean flags | `한글법령여부`, `별표편집여부`, `공포법령여부`, `제명변경여부`, `언어` | Effectively constant across the Phase-1 corpus (Act + Decree both observed). Low information value. Promote individually if a query ever needs one. |
| Deliberately not stored (per ERD draft) | `연락부서`/`부서단위`, `전화번호`, `개정문내용`, `법령명_한자`, `공동부령정보` | ERD already documents these as omitted with reasoning ("not relevant to retrieval, can be reconstructed from API"). JSONB silently captures them and contradicts that policy. |
| Phase-2 amendment tracking | `조문이동이전`, `조문이동이후` (article-level) | Belongs to TODO-5 (`node_id` retention across amendments), not TODO-8. |
| Trivially derivable | `법령키` root attribute | Concatenation of existing columns. |

The unmapped surface is **small, categorically known, and
predictable** — not the "unknown evolving metadata" shape that
justifies a JSONB column.

Important asymmetry between the two candidate tables:

| Table | Phase-1 row count | Phase-4 plausible row count | On chunks query path |
|-------|-------------------|------------------------------|----------------------|
| `legal_documents` | 2 (Act + Decree) | low thousands | No |
| `structure_nodes` | hundreds per document | hundreds of thousands | Yes (via FK from `chunks`) |

Putting JSONB on `structure_nodes` would impose a real
performance tax on the chunks-join path for zero identified benefit
(every node-level field — number, title, content, level, sort_key,
effective_date, is_changed — is uniformly structured).

## Decision

**No JSONB `metadata` column on `legal_documents`.**
**No JSONB `metadata` column on `structure_nodes`.**

The forward policy on statute-table fields is the one already
implicit in the ERD draft, now ratified by this ADR:

1. **Promote** an API field to a typed column when it earns its
   keep — answers a query, drives a constraint, or carries
   evaluation/provenance value.
2. **Omit deliberately** with a reasoned entry in the ERD's
   "Not stored" list.
3. **Retain** raw API XML responses as the canonical fallback
   for any field we later decide to promote.

The third point is a soft dependency on a retention commitment that
is not currently formalized as its own ADR (see "Trade-offs accepted"
below).

## Options considered

| Option | Verdict |
|--------|---------|
| **A. No JSONB on either table** | **accepted** |
| B. JSONB `metadata` on both `legal_documents` and `structure_nodes` | rejected — see "vs. B" |
| C. JSONB `metadata` only on `legal_documents` (catch-all) | rejected — see "vs. C" |
| D. JSONB on `legal_documents` with a named-field allowlist (not catch-all) | rejected as primary; held as fallback if raw-XML retention is ever explicitly *not* committed |

### Why A over C — the strongest competitor

C ("JSONB only on `legal_documents`, catch-all for fields we don't
promote") is the steelman because document-level metadata is
demonstrably more variable than node-level, and `legal_documents` is
small enough that the storage tax is irrelevant. The arguments **for**
C:

1. **Cheap insurance.** If we discover later we need a field we
   discarded, and we no longer have the raw XML, JSONB recovery is a
   `WHERE metadata->>'field' IS NOT NULL` query rather than a
   re-fetch.
2. **Document-level metadata is genuinely variable** across law
   types. Other 법령 categories (행정규칙, 자치법규) and other
   API endpoints could surface fields not present today. JSONB
   absorbs them without schema migration.
3. **ADR-007's `doc_type_code` argument applies asymmetrically.**
   Capture-on-the-parse-path is cheap; recovery is expensive. JSONB
   generalizes that to the whole document-level surface.

The arguments **against** C (and why A wins):

1. **The candidate fields fail the JSONB-shape test.** ADR-007's
   own framing: "JSONB is the right shape for *unknown* metadata,
   not *known* single fields. When you know exactly which field you
   want to capture and how it's queried, a typed column beats a JSON
   property on every dimension." The TODO-8 candidate fields
   (연락부서, 개정문내용, 법령명_한자, the boolean flags) are all
   known. If we want them, promote them.
2. **Catch-all JSONB undermines the ERD's existing discipline.**
   The ERD draft documents *every* field with a confidence marker
   and a rationale, including the "Not stored" list which carries
   reasoning per omitted field. A JSONB column shifts this policy
   from "promote or omit, with reasoning" to "promote or stash
   silently." That regression is the exact JSONB-as-junk-drawer
   anti-pattern the working agreements warn against.
3. **The "cheap insurance" argument is served by raw-XML
   retention, not JSONB.** If we keep the raw API responses
   (which we already do for samples in `docs/api-samples/`), any
   later promotion is a re-parse, not a re-fetch. The marginal
   value of JSONB-over-XML-retention is a query convenience that
   doesn't justify the policy shift in (2).
4. **Provenance is served by `content_hash` + `source_url` +
   raw-XML retention.** ADR-007's provenance argument applied to a
   *known stable identifier* with downstream eval-harness use cases.
   The TODO-8 candidate fields are not eval-relevant. If a
   field becomes eval-relevant, that is the trigger for promoting
   it to a column.
5. **The variability premise is weaker than it looks.** Other law
   types (행정규칙, 자치법규) are explicitly out of Phase 1. When
   they enter scope (Phase 2+), the right move is a focused review
   of the new field surface — exactly the moment to promote new
   columns, not to retroactively justify a JSONB column added
   speculatively in Phase 1.

### Why A over B — JSONB on both tables

Everything in "A over C" plus:

1. **Row-count tax.** `structure_nodes` is on the chunks-join path
   and grows with corpus size. JSONB on it for zero identified
   benefit is the wrong cost trade.
2. **Node-level structure is uniform.** Every promoted field on
   `structure_nodes` (number, title, content, level, sort_key,
   effective_date, is_changed) is uniformly structured across all
   observed nodes. There is no JSONB candidate field on this
   table even under the most permissive reading.

### Why A over D — limited JSONB with named-field allowlist

D would put `metadata JSONB` on `legal_documents` and populate it
only with named fields (e.g., `{"raw_amendment_text": "...",
"contact_dept": [...]}`).

D's appeal: keeps the discipline (no silent capture) while still
hedging against raw-XML retention not being committed.

Why D loses as primary:

1. **If you know the field, promote it.** A named-field allowlist
   in JSONB is a column with worse ergonomics — no type, no
   B-tree, ORM friction. The only thing it buys is a migration
   skip when adding a new field, which is a minor convenience.
2. **It is a worst-of-both posture.** It signals JSONB without
   committing to JSONB's strength (schema-flexible capture) — and
   pays JSONB's cost (query ergonomics, ORM friction) for known
   fields.
3. **The "no committed retention" condition that justifies D is
   itself a separate decision** that should be made on its
   merits. ADR-008 declines to short-circuit it via JSONB.

D is held as the fallback if Phase-1 closes without a raw-API-XML
retention commitment landing. In that case ADR-008 is revisited.

## Trade-offs accepted

- **Soft dependency on raw API XML retention.** The "no JSONB"
  policy presumes that if we later need a field we currently omit,
  we can re-derive it from the original API response. This requires
  raw API responses to remain replay-available — either retained on
  disk by the ingestion pipeline or re-fetchable from
  `lawService.do`. Currently `docs/api-samples/` holds samples
  manually; there is no formal pipeline-level retention commitment.
  ADR-008 flags this dependency. If a future architectural decision
  forecloses retention (e.g., compliance-driven deletion), ADR-008
  is revisited and Option D becomes the fallback.
- **Cannot capture unknown future fields silently.** If 법제처
  ever adds a new element to law-detail responses, the ingestion
  parser will silently drop it until we update the parser. This is
  the same risk the project already accepts for every column-based
  schema; ADR-008 does not change it.
- **Minor backfill cost if a field is promoted later.** Promoting a
  field requires (a) updating the parser, (b) re-running the
  ingestion pipeline against retained raw XML, (c) adding the
  column. With JSONB, the equivalent backfill is a `metadata->>` →
  column extraction — slightly cheaper. Accepted.

## Consequences

- ERD draft `TODO-8` flips to ✅ RESOLVED with a pointer to ADR-008.
- ERD draft `legal_documents.legislation_reason` row drops the
  "(see TODO-8 on JSONB)" comment — storage is committed as a
  column. Size discipline is left to the column comment.
- ERD draft `Open Items` count drops from 5 (TODO-2, 5, 7, 8, 10)
  to 4 (TODO-2, 5, 7, 10).
- `Next Steps` list at the bottom of the ERD draft is refreshed to
  reflect TODO-8 closure.
- ADR-007's "Why B over C" §1 currently leans on "TODO-8 is
  unresolved." A forward-pointer is added noting that TODO-8 is now
  resolved by ADR-008 and *does not* introduce JSONB on
  `legal_documents`, so ADR-007's option-C rejection holds for an
  additional reason: there is no JSONB target for `doc_type_code` to
  land in.
- No DDL changes (no columns added or removed).
- The implicit policy "promote when needed, omit deliberately,
  retain raw responses" is now explicit — and forward-applicable to
  the four other category ERDs without re-litigation.

## Verification once accepted

1. ERD draft TODO-8 marked ✅ RESOLVED with ADR-008 pointer; "Open
   Items" reduced to TODO-2, 5, 7, 10.
2. `legislation_reason` field row in the ERD draft no longer
   references "TODO-8 on JSONB."
3. `Next Steps` section updated.
4. ADR-007 "Why B over C" §1 carries a forward-pointer to ADR-008.
5. CLAUDE.md §4 updated to reflect ADR-008 acceptance and the
   shrunken open-TODO list.
6. No changes to ADR-001 through ADR-006 invariants:
   - ADR-002 five-table list — unchanged.
   - ADR-003 chunks DDL FK columns — unchanged.
   - ADR-006 `doc_type` / `level` representation — unchanged.

## Revisit triggers

ADR-008 is revisited if any of the following hold:

- **Raw-API-XML retention** is explicitly *not* committed (e.g.,
  pipeline design forecloses storage). Fallback: Option D
  (named-field allowlist JSONB on `legal_documents`).
- **An unmapped field demonstrates eval-harness or
  retrieval-pipeline value** that cannot wait for a column-promotion
  cycle. Action: promote that specific field, not introduce JSONB.
- **A different category ERD** (사법판단 / 유권해석 / 학술자료 /
  입법개정자료) surfaces a genuinely schema-on-read field surface
  whose shape is not knowable in advance. Each category gets its
  own ADR; ADR-008's policy is statute-scoped but the reasoning is
  generalizable.

## References

- `docs/legal-erd-draft.md` — TODO-8 specification; "Not stored
  (deliberate omissions)" list on `legal_documents`
- `docs/decisions/ADR-007-doc-type-code-capture.md` — sibling-column
  pattern; "Why B over C" §1 (the explicit TODO-8 forward dependency)
- `docs/phase-1-progress.md` §5 — `chunks.metadata` JSONB agreement
  (out-of-scope reference for "JSONB is allowed where the schema is
  genuinely emergent")
- `docs/api-samples/law-228817-중대재해처벌법.xml` — Act XML;
  evidence for the "small unmapped surface" claim
- `docs/api-samples/law-277417-중대재해처벌법시행령.xml` — Decree
  XML; same
