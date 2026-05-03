# ADR-012 — `structure_nodes` keying convention for sub-조 levels + `sort_key` format

- **Status**: Accepted
- **Date**: 2026-05-03
- **Context layer**: Statute (성문규범) ERD — `structure_nodes` table
- **Resolves**:
  - Gap left by ADR-002 for levels 6–8 (항/호/목), where ADR-002's
    "Natural-key source: `<조문단위 조문키>`" is silent. 호 has its
    own `<호번호>` + `<호가지번호>` API elements that need composition;
    항 / 목 have no native key and need ordinal derivation.
  - ERD-draft "Sketch" status of `sort_key` (line 200).
  - Implicit-항 policy (encountered in Act §2 XML; previously
    undocumented).
  - Branch numbering scope (per
    *법령의개정방식과폐지방식*: 조 and 호 only, two distinct API
    encodings; verified empirically). Was wrongly framed as deferred
    in the initial draft.
- **Depends on**:
  - **ADR-002 (Accepted)** — `node_key` for levels 1–5 = `<조문단위 조문키>`.
    This ADR extends the convention to levels 6–8 *without* contradicting
    ADR-002.
  - **ADR-006 (Accepted)** — level mapping (1=편..8=목).
  - **ADR-008 (Accepted)** — no JSONB fallback; every promoted concept
    becomes a column or a key.
  - **ADR-010 (Accepted)** — Phase-1 DDL freeze. This ADR commits values
    to populate existing `structure_nodes` columns; no schema change.
- **Forward-pointer**: TODO-5 (node_id retention across amendments). The
  keying convention chosen here must be stable across re-ingest and
  ideally across amendments. Keys derived from API content (조문키 +
  ordinal position at 항/목, parsed 호번호+호가지번호 at 호) — never
  from ingestion-time global counters — keep this ADR out of TODO-5's
  revisit path, except for the explicit caveat in Trade-offs §4.

## Context

`structure_nodes` is the unified hierarchy table for statute bodies
(편/장/절/관/조/항/호/목 → levels 1..8 per ADR-006). ADR-002 settled
`(doc_id, node_key)` as the natural-key UNIQUE constraint, with `node_key`
sourced from `<조문단위 조문키>`. That works for levels 1–5: the API
emits `<조문단위>` with a `조문키` attribute for both heading rows
(`<조문여부>전문</조문여부>`, e.g., `0003000`) and article rows
(`<조문여부>조문</조문여부>`, e.g., `0003001`). The `xxx000` / `xxx001`
discipline naturally encodes heading-before-article ordering.

It does **not** work for levels 6–8. 항/호/목 are nested *inside*
조문단위 in the XML and carry no API-native key. Empirical inspection of
`data/raw/013993/228817.xml` (Act) and `data/raw/014159/277417.xml`
(Decree) confirms the structure:

- 항: `<항>` element. Sometimes carries `<항번호>` (circled CJK digit,
  e.g., `①` `②`), sometimes does not — the latter when the 조 has
  only one paragraph and the body lives in `<조문내용>` directly
  (Act 제2조, lines 79–95).
- 호: `<호>` with `<호번호>` (decimal, e.g., `1.` `2.`).
- 목: `<목>` with `<목번호>` (Korean alphabet, e.g., `가.` `나.`).

Three things must be decided to populate `structure_nodes` end-to-end:

1. **`node_key` format for levels 6–8** — must be unique within
   `(doc_id, node_key)` and stable across re-ingest.
2. **`sort_key` format for all levels** — must give correct lexical
   order under document traversal, including (a) heading-before-article
   ordering already encoded by ADR-002, (b) skipped levels (e.g.,
   중대재해처벌법 has no 편 / 절 / 관), and (c) future branch
   numbering (`제39조의2의2`) when first observed.
3. **Implicit 항 policy** — when the API emits a bare `<항>` with no
   `<항번호>`, do we materialize an implicit row at level 6, or attach
   호 directly to 조 (skipping the level)?

## Decision

### 1. `node_key` for levels 6–8

Per §4: **branch numbering occurs at 조 (level 5) and 호 (level 7)
only** — never at 편/장/절/관/항/목 — per the official 법제처
reference "법령의개정방식과폐지방식," cross-checked against the
도로교통법 (mst=281875) and 형법 (mst=284025) samples. The keying
convention reflects that asymmetry directly:

Tagless ASCII shape — segment count after `{조문키}` is bijective with
level (per the §1 table; ADR-006 also has it in the `level` column):

| Level | Format | Example |
|-------|--------|---------|
| 1–4 (편/장/절/관) | `{조문키}` (전문 row) | `0003000` |
| 5 (조) | `{조문키}` (API encodes 조문가지번호) | `0003001`, `0104021` (제104조의2) |
| 6 (항) | `{조문키}-{HH}` (ordinal) | `0002001-00` (implicit), `0004001-01` (① 1st 항) |
| 7 (호) | `{조문키}-{HH}-{NN}{BB}` | `0001001-01-0700` (제7호), `0001001-01-0702` (제7호의2) |
| 8 (목) | `{조문키}-{HH}-{NN}{BB}-{KK}` (ordinal at level 8) | `0002001-00-0200-01` |

Per-level keying rules:

- **Levels 1–5** use the API's `<조문단위 조문키>` verbatim; the API
  itself encodes 조문가지번호 into 조문키 as a 7-digit pattern (see §4).
  Branched articles get distinct keys for free.
- **Level 6 (항)** uses positional ordinal `HH` (00 reserved for
  implicit 항 — `<항>` with no `<항번호>`; explicit 항 numbered from 01).
  Ordinal — not the displayed `<항번호>` value — because circled CJK
  digits (① ②) need no normalization round-trip and the document order
  is the ground truth. 항 does not branch (verification trigger if it
  ever does — see §4).
- **Level 7 (호)** uses `{NN}{BB}` (4-digit segment, no separator
  inside) where:
  - `NN` = `<호번호>` parsed and zero-padded to 2 digits
    (e.g., `7.` → `07`, `21.` → `21`).
  - `BB` = `<호가지번호>` zero-padded to 2 digits, or `00` when the
    element is absent (non-branched 호).

  This mirrors the 7-digit 조문키 shape (`{NNNN}{BB}{T}` for 조;
  `{NN}{BB}` for 호) — the parser synthesizes for 호 what the API
  synthesizes inside 조문키 for 조. Concatenated rather than
  separator-delimited inside the segment to keep `NN`+`BB` visually
  one unit and the dash-separator semantics consistent across levels.
- **Level 8 (목)** uses positional ordinal `KK`. 목 does not branch
  (verification trigger if it does).

The displayed `호번호` / `목번호` lives in the `number` column, not
the key. Two columns, two roles. Korean level tags (`항`/`호`/`목`)
were considered as visual prefixes but rejected — see §Options C₁;
the level info is already in the `level` column.

### 2. `sort_key`

Single padded string, lexically sortable, format-derived from `node_key`:

| Level | Format | Example |
|-------|--------|---------|
| 1–5 | `{조문키}` (7-digit, zero-padded) | `0003000`, `0003001`, `0104021` |
| 6 | `{조문키}.{HH}` | `0002001.00`, `0004001.01` |
| 7 | `{조문키}.{HH}.{NN}{BB}` | `0001001.01.0700` (호 7), `0001001.01.0702` (호 7의2) |
| 8 | `{조문키}.{HH}.{NN}{BB}.{KK}` | `0002001.00.0200.01` |

Lexical sort places shorter prefixes before longer with the same prefix
(`0002001` < `0002001.00` < `0002001.00.0200`), giving the correct
document order: chapter heading → article → article's first 항 → first
호 of that 항 → first 목 of that 호. Heading-before-article inside the
same 조문번호 is already encoded by the API's `xxx000` < `xxx001`
discipline. Branched 호 (`호0702`) sort between their main and the
next main 호 (`0700` < `0702` < `0800`).

Punctuation-only segment separator (`.`) is chosen over `-`/`_` because
`.` (ASCII 46) is the single dominant choice for hierarchical numbering
in Korean legal citation conventions, and ASCII-collation places it
just below digit ASCII (`0`–`9` is 48–57), preserving the desired sort.

### 3. Implicit 항 policy

When the API emits `<항>` with no `<항번호>`, **materialize an implicit
항 row at level 6**:

- `node_key = {조문키}-00`
- `sort_key = {조문키}.00`
- `number = ''` (empty string — schema's `NOT NULL` is satisfied)
- `content = ''` (empty — the body text lives on the parent 조's
  `<조문내용>`, stored on the 조 row, not duplicated)

Reasoning: preserves the level invariant — every 호 has a level-6
parent, every 목 has a level-7 parent. Without an implicit 항, level-7
호 would have a level-5 조 parent, which breaks any
"give me all 항 inside this 조" query and complicates the renderer.

### 4. Branch numbering — settled at 조 and 호 only

**Policy source.** Per the official 법제처 reference
*법령의개정방식과폐지방식* (cited authoritatively by Seheon),
branch numbering ("제X…의Y" form) applies at **exactly two
levels — 조 and 호**. Authoritative enumeration:

| Pattern | Level | Status |
|---------|-------|--------|
| 제X편의Y / 제X장의Y / 제X절의Y / 제X관의Y | 1–4 | **NOT accepted** (above 조) |
| 제X조의Y (e.g., 제5조의2) | 5 (조) | **ACCEPTED** — encoded in `조문키` (§4a) |
| 제X항의Y (e.g., 제1항의2) | 6 (항) | **NOT accepted** |
| 제X호의Y (e.g., 제1호의2) | 7 (호) | **ACCEPTED** — composed by parser (§4b) |
| 제X목의Y | 8 (목) | **NOT accepted** (below 호) |

This ADR commits to exactly that scope. The verification trigger
in §4c halts ingestion if the corpus ever produces a branch
element at any "NOT accepted" level — defensive boundary against
the policy being wrong or amended after the citation.

#### 4a. 조-branches (level 5)

Empirical inspection of 형법 (`mst=284025`) and 도로교통법
(`mst=281875`) shows the API encodes 조-branches directly into
`조문키` as a 7-digit fixed-width pattern:

```
조문키 = {NNNN}{BB}{T}
  NNNN = 조문번호, zero-padded 4 digits
  BB   = 조문가지번호, zero-padded 2 digits ("00" for non-branched)
  T    = 1 for article (조문여부=조문)
         0 for chapter heading (조문여부=전문)
```

Evidence: 형법 has 49 `<조문가지번호>` instances incl. 제116조
with branches 2 + 3 (keys `0116021` / `0116031`). 도로교통법 has
49 `<조문가지번호>` instances. Unbranched samples in
중대재해처벌법 fit the same pattern with `BB=00` (`0001001` =
1/00/1). All observed `BB` values ≤ 5; `T` ∈ {0, 1}.

**Decision: use API `조문키` verbatim** as `node_key` and the
`sort_key` prefix for level 5, exactly as ADR-002 specified. No
schema-side extension. Lexical sort: `0116001` < `0116021` <
`0116031` < `0117001`.

#### 4b. 호-branches (level 7)

Structurally distinct from 조-branches: the API does **not** mint
a unique key for branched 호. Instead, branched 호 appears as a
sibling `<호>` element with the *same* `<호번호>` value as its
parent 호 plus a `<호가지번호>` element marking the branch index.
Example from 도로교통법 (lines 133–138):

```xml
<호>
  <호번호><![CDATA[7.]]></호번호>
  <호내용>7. ...</호내용>
</호>
<호>
  <호번호><![CDATA[7.]]></호번호>          ← parent 호 number
  <호가지번호><![CDATA[2]]></호가지번호>     ← branch index
  <호내용>7의2. ...</호내용>
</호>
```

Evidence: 도로교통법 has 37 `<호가지번호>` instances spanning
호 7의2, 13의2, 18의3, 21의3, 호번호 ∈ at least {7, 13, 18, 21,
…} with 가지번호 ∈ {2, 3, 4, 5}. 형법 has 0 호-branches —
explains why my prior single-sample analysis missed this.

**Decision: compose `{NN}{BB}`** as the level-7 segment, where `NN`
is `<호번호>` zero-padded 2 digits and `BB` is `<호가지번호>` zero-padded
2 digits (`00` when absent). The parser synthesizes for level 7 what
the API synthesizes inside 조문키 for level 5 — same shape, different
source.

Lexical sort: `0700` (호 7) < `0702` (호 7의2) < `0703` (호 7의3) <
`0800` (호 8). Correct document order. Within the full key:
`0001001-01-0700` < `0001001-01-0702` < `0001001-01-0800`.

#### 4c. Verification trigger (defensive boundary)

Two assertions fire on every ingest. Mismatch → halt, revisit ADR.

1. **`조문키` shape.** Must match `^[0-9]{7}$`; decoding
   `NNNN`/`BB`/`T` must agree with `<조문번호>` /
   `<조문가지번호>` / `<조문여부>`. Catches:
   - Wider keys for unobserved nesting (e.g., 의X의Y if it ever
     ships with extended encoding).
   - `BB` overflow beyond 99 (2-digit cap, theoretically reachable
     but not observed).
   - API contract drift.
2. **No branches outside 조 / 호.** Any `<항가지번호>`,
   `<목가지번호>`, `<편가지번호>`, `<장가지번호>`, `<절가지번호>`,
   `<관가지번호>` element triggers a halt. Catches the case where
   *법령의개정방식과폐지방식* is wrong or has been amended since
   the citation.

The verification is a defensive boundary, not deferral: the
decision is made (조 and 호 only, encoded as above); the triggers
catch the case where input shape changes underneath us.

## Options considered

### node_key for 항/호/목

| Option | Format | Verdict |
|--------|--------|---------|
| A | Position only with literal level number — `{조문키}.6.{HH}.{NN}.{KK}` (level digit baked into key) | rejected — encoding level number twice (level column + key digit) is redundant |
| B | Use displayed `호번호` / `목번호` directly — `{조문키}-1.-가.` | rejected — punctuation in keys, locale-sensitive collation (가/나/다 vs ㄱ/ㄴ/ㄷ), mismatched encoding when API rendering varies |
| C₀ | Korean level-tag prefixes — `{조문키}-항{HH}-호{NN}{BB}-목{KK}` | rejected — non-ASCII keys hurt URL/log/regex tooling; tags duplicate the `level` column; visually heavier without identity gain |
| C₁ | Tagless pure-ordinal at every sub-level — `{조문키}-{HH}-{NN}-{KK}` (NN = positional ordinal of 호) | rejected for 호 — discards the API's `<호번호>` + `<호가지번호>` signal that distinguishes branched 호 from sequentially-numbered ones; ordinal collapses both into the same shape |
| **C₂** | **Tagless hybrid — `{조문키}-{HH}-{NN}{BB}-{KK}` (HH/KK ordinal at 항/목, NN+BB parsed `<호번호>`+`<호가지번호>` at 호)** | **accepted** — ASCII-only, mirrors the API's own asymmetry; 호-branch identity preserved without 항/목 false-precision |
| D | Path string of source XML offsets — `{조문키}@{xpath_index}` | rejected — opaque, breaks if API element ordering shifts between fetches |
| E | Hash of node content | rejected — content changes across amendments; key would not be stable |

### sort_key

| Option | Format | Verdict |
|--------|--------|---------|
| α | Pure document-traversal counter — global integer incremented per row | rejected — not derivable from content; ingestion-time only; un-resumable; breaks under partial re-ingest |
| β | 8 fixed dot-separated segments (one per level), zero-padded | rejected — most segments are `00` for typical 조-only statutes; verbose, hides the API's natural 7-digit prefix |
| **γ** | **Variable-length: `{조문키}` + `.{HH}` per descended sub-level** | **accepted** |
| δ | Reuse `node_key` directly as `sort_key` (drop the column) | rejected for Phase-1 — ADR-010 freeze keeps both columns; `sort_key` exists and must be populated. Becomes the **Phase-2 follow-up** per §Consequences once tagless `node_key` makes the redundancy explicit |

### Implicit 항

| Option | Behavior | Verdict |
|--------|----------|---------|
| **i** | **Materialize implicit 항 row at level 6** | **accepted** — preserves level invariant |
| ii | Skip implicit 항; attach 호 directly to 조 | rejected — breaks parent_id-level relationship; level-7 row with level-5 parent complicates "all 항 of this 조" queries |
| iii | Demote 항 to a virtual concept; merge content into 조's `content` | rejected — collapses retrievability; can't index 호/목 separately from 조 lead-in |

## Why C₂ / γ / i

1. **Stability across re-ingest.** Both `node_key` and `sort_key` are
   derived from API-emitted content (조문키 verbatim at levels 1–5;
   ordinal position within parent at 항/목; parsed 호번호+호가지번호
   at 호). A re-fetch produces identical keys as long as the API returns
   elements in document order — which is the API contract. Pairs cleanly
   with the `_skip_if_present`-style idempotent re-ingest path.
2. **Lexical sort matches document order.** The 7-digit `조문키` already
   encodes heading-before-article (`xxx000` < `xxx001`); sub-level dot
   extensions extend the order naturally; shorter strings sort before
   their longer-prefixed children.
3. **No JSONB / no schema change.** Every value lives in existing
   `node_key TEXT NOT NULL` and `sort_key TEXT NOT NULL` columns under
   ADR-010's freeze; this ADR is purely a population-rule decision.
4. **Stays out of TODO-5's amendment-tracking decision.** Keys derived
   from API content only, never from ingestion order. When TODO-5
   lands, the keying convention here doesn't have to change; only the
   row-versioning policy does. (See Trade-off §4 below for the residual
   risk.)

## Trade-offs accepted

1. **`sort_key` is variable-length.** Lexical sort still works, but
   range queries like "give me everything between 0002001 and 0003000"
   don't trivially scope sub-levels of 0002001 in or out. Consumers
   must use prefix queries (`sort_key LIKE '0002001%'`) and the
   `level` column for level-bounded filtering, not naive range scans.
2. **Implicit 항 rows contain empty `content`.** BM25 documents with
   empty content are inert (zero score). Acceptable — we don't want
   implicit 항 to appear in retrieval results anyway; the substantive
   content lives on the parent 조 row.
3. **Ordinal `HH` / `NN` / `KK` is not the displayed `호번호` /
   `목번호`.** That is by design: identity (key) and display (number)
   are separate columns. If a statute renders 호 as `1.` `2.` `3.`
   for its first three items but jumps to `5.` for the fourth (real
   pattern in some amended statutes), the ordinal stays `01` `02` `03`
   `04` while `number` carries `1.` `2.` `3.` `5.`. Better than the
   alternative (key drift).
4. **Amendment fragility — partial.** If an amendment inserts a new
   호 between existing 호1 and 호2, the API ordinal positions of the
   downstream 호 shift by one, so their `node_key` / `sort_key`
   change. This means `node_key` is *not* a stable cross-amendment
   identifier for sub-조 nodes. ADR-002 raised this issue for
   `node_id` itself (TODO-5 territory); this ADR inherits and does
   not resolve it. The chosen convention is no worse than the
   alternatives — Option E (content hash) was actually worse here
   (text changes invalidate the key even when position is stable);
   only positional encoding has any chance of stability across the
   common case where amendments append at the end. Real solution
   waits on TODO-5.
5. **Branch numbering: settled at 조 and 호 only, two encodings.**
   Per 법령의개정방식과폐지방식, branches occur at 조 and 호 only
   (verified empirically against 형법 and 도로교통법). 조-branches
   ride inside `조문키`; 호-branches use `<호번호>` + `<호가지번호>`
   composed by the parser. Verification triggers catch (a) API
   contract drift on either encoding, (b) any branch element at
   levels we don't expect. See §4.

## What was checked vs. what is still open

| Hypothesis | Sample inspected | Result |
|-----------|------------------|--------|
| 조문단위 has 조문키 attribute for 전문 + 조문 forms | Act + Decree | ✅ confirmed — `0003000` (heading) / `0003001` (article) pattern observed |
| 항 may be present without 항번호 | Act §2 (lines 79–95) | ✅ confirmed — bare `<항>` wraps 호 children, no 항번호 |
| 항 with 항번호 uses circled CJK digits (① ② …) | Decree §3 (lines 290–296) | ✅ confirmed |
| 호 always has 호번호 | Act + Decree, sampled articles | ✅ confirmed in inspected articles; **not stress-tested** across all 호 elements |
| 목 always has 목번호 | Act §2, §4 | ✅ confirmed in inspected articles; **not stress-tested** |
| 조-branch encoding via 조문키 | 형법 (49 instances incl. 제116조 가지∈{2,3}), 도로교통법 (49 instances) | ✅ confirmed — `xxxx{BB}{T}` pattern holds |
| 호-branch encoding via `<호가지번호>` | 도로교통법 (37 instances, 가지번호 max=5, e.g., 호 7의2, 13의2) | ✅ confirmed — sibling `<호>` with same `<호번호>` + `<호가지번호>` |
| 항-branch absence | 도로교통법 (0 `<항가지번호>` elements), 형법 (0) | ✅ confirmed |
| 목-branch absence | 도로교통법 (0 `<목가지번호>`), 형법 (0) | ✅ confirmed |
| 편/장/절/관-branch absence | both samples (0 of each) | ✅ confirmed |
| Nested branches (의X의Y) at 조 level | none observed | ⚠️ **not exercised** — verification trigger fires if encountered |
| 호번호 max value | 도로교통법 references up to 호 21 in CDATA | partial; **not stress-tested** for 호번호 > 99 (2-digit `NN` cap) |

The not-stress-tested items above are API-contract assumptions
consistent with the inspected samples. **If a 호 turns out to lack
`<호번호>` in some statute, the parser hard-fails** rather than
falling back to ordinal — the 호-key composition rule depends on
the API providing 호번호. That's surfaced via verification trigger
§4c.1, not silently absorbed. For 목 (where ordinal `KK` is the
key), missing 목번호 is non-fatal — only the `number` column goes
empty.

## Consequences

- The XML parser (deferred from the 2026-05-03 walking skeleton)
  implements the keying rules above. No schema migration; the work
  lives in `src/ingest/` (`_insert_children` and friends).
- `sort_key` column populated for every row. Inserts construct keys
  deterministically without a self-SELECT — no race, no row-order
  dependency.
- ADR-002's "Natural-key source" line for `structure_nodes` extends
  from `<조문단위 조문키>` to "조문키 + tagless positional segments
  for descendants (ordinal at 항/목; parsed 호번호+호가지번호 at 호)."
  Forward-pointer added to ADR-002.
- TODO-5 (amendment-tracking) revisits the "stable across amendments"
  claim when it lands — see Trade-off §4. Mitigation TBD by TODO-5's
  design.
- Verification triggers (§4c) are implemented in `src/ingest/parse.py`
  alongside the existing `doc_type` check (ADR-006). Two assertions:
  one per ingested 조문단위 (조문키 shape + decoded fields agreement),
  one per descended sub-element (no `<항가지번호>` / `<목가지번호>` /
  level-1..4 가지번호). Halt-on-violation, not warn — the convention
  is load-bearing.
- **Phase-2 follow-up.** Under the tagless `node_key` encoding,
  `sort_key = REPLACE(node_key, '-', '.')` exactly. `sort_key`
  carries no information `node_key` doesn't, and `ORDER BY node_key`
  would give the same result. The column is preserved for Phase-1
  only — ADR-010's freeze blocks destructive change. **Recommended
  Phase-2 follow-up**: a separate ADR that drops `sort_key`, switches
  retrieval queries to `ORDER BY node_key`, and updates downstream
  tooling. Trigger: Phase-1 → Phase-2 transition when corpus expands
  beyond 중대재해처벌법. The implementation tax during Phase-1: a
  single `_compose_keys()` returning `(node_key, sort_key)` from one
  base string, separator-translated. When the Phase-2 ADR drops
  `sort_key`, that function returns `node_key` only; mechanical
  refactor.

## References

- `migrations/001_statute_tables.sql` — frozen `structure_nodes`
  schema this ADR populates
- `docs/legal-erd-draft.md` §structure_nodes — `node_key` Resolved,
  `sort_key` Sketch, line 218 same-number duplication note
- `docs/decisions/ADR-002-identifier-strategy.md` — `node_key` for
  levels 1–5
- `docs/decisions/ADR-006-doc-type-and-level-enums.md` — level
  mapping 1..8
- `docs/decisions/ADR-008-jsonb-on-statute-tables.md` — no JSONB
  fallback policy
- `docs/decisions/ADR-010-phase-1-ddl-freeze.md` — schema freeze
- `data/raw/013993/228817.xml` — Act (중대재해처벌법), source for
  항-without-항번호 pattern (§3)
- `data/raw/014159/277417.xml` — Decree (시행령), source for
  항-with-항번호 pattern (§3)
- `data/raw/001692/284025.xml` — 형법, source for 조-branch
  encoding (§4a); 49 `<조문가지번호>` instances, 가지번호 ∈ {2, 3}
- `data/raw/001638/281875.xml` — 도로교통법 (mst=281875,
  공포번호=21246, 시행 2026-04-02), source for 호-branch encoding
  (§4b); 37 `<호가지번호>` instances, 가지번호 max=5
- 법제처 reference *법령의개정방식과폐지방식* — policy source
  for "branches at 조 and 호 only" (§4)
