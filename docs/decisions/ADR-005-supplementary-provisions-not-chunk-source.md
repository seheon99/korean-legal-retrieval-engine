# ADR-005 — `supplementary_provisions` is **not** a chunk source in Phase 1

- **Status**: Accepted
- **Date**: 2026-04-26
- **Context layer**: Search-index layer (chunks) × Statute (성문규범) ERD
- **Resolves**: ADR-004 deferred Q1 (chunk-source status of
  `supplementary_provisions`); flushes the unstated assumption inside
  ADR-003's chunks DDL (`provision_id` is omitted without an explicit
  argument).
- **Depends on / aligned with**: ADR-001 (split-table precedent: forms
  excluded from chunks on retrieval-quality grounds), ADR-003 (chunks
  DDL stays unchanged under this decision; the per-source-family
  extension pattern is preserved as the future-revisit path), ADR-004
  (placement decided — 부칙 lives in `supplementary_provisions`)
- **Out of scope (downstream decisions, not decided here)**:
  1. Whether to add a `kind` column on `supplementary_provisions`
     distinguishing 제정 vs 일부개정. Coupled with selective indexing
     (Option B); deferred again because Option B is rejected here.
  2. How to internally parse `부칙내용` (제N조 inside the CDATA blob).
     Parsing/granularity decision; would only become live if a future
     ADR overturns this one.

## Context

ADR-004 settled placement (separate table) but explicitly deferred the
chunk-source question. ADR-003's chunks DDL lists exactly two Phase-1
statute FK columns — `structure_node_id` and `annex_id` — and has no
`provision_id`. That omission is the **current implicit default**, but
ADR-003 did not argue it; ADR-004 flagged it as the "live default
without an argument."

This ADR makes that omission load-bearing.

The decision matters because:

- The chunks-side schema and the CHECK constraint either grow by one
  branch or do not. ADR-003 explicitly accepted "CHECK-constraint
  complexity grows with category count" as a trade-off; the question
  is whether 부칙 earns that complexity.
- The retrieval pipeline's Phase-1 evaluation baseline depends on
  which sources are chunk-indexed. Adding 부칙 now means the baseline
  measures a different system than the one that excluded 부칙. That
  shapes what we can reason about empirically.
- 부칙 is a non-trivial slice: 1 row on the Act, 6 rows on the Decree
  in Phase-1 scope, with a wide signal-to-noise spread across rows.

## Empirical basis (verified 2026-04-26 — extends ADR-004's table)

| Question | Finding | Source |
|----------|---------|--------|
| What does the **Act** 제정 부칙 actually contain? | Two sub-clauses: `제1조(시행일)` — phased enforcement (1년 default + 3년 carve-out for individual sole proprietors and 50명 미만 사업장; 50억 미만 construction); `제2조(다른 법률의 개정)` — adds `아목` to 법원조직법 제32조제1항제3호. | Act XML lines 660–675 |
| What does the **Decree** 제정 부칙 contain? | Single sentence: "이 영은 2022년 1월 27일부터 시행한다." Effective-date only. | Decree XML lines 796–802 |
| What do the **Decree's 5 amending 부칙** contain? | Each is a "다른 법령의 개정" cross-amendment from a non-related regulatory package. Most clauses are elided ("①부터 ⑭까지 생략"); each retains a **single-line textual diff** against this Decree. | Decree XML lines 805–938 (5 entries: 도서관법 시행령, 화학물질관리법 시행령, 관광진흥법 시행령, 기후에너지환경부 직제, 고용노동부 직제) |
| Are there content duplicates across amending 부칙 rows? | Yes — `부칙키=2025100135804` and `부칙키=2025100135805` (both dated 2025-10-01, from different regulatory packages) make the **same textual change**: `"환경부장관"` → `"기후에너지환경부장관"` against `제8조제1호다목 및 같은 조 제2호다목`. | Decree XML lines 904, 931 |
| Does any amending 부칙 mention the law it amends *into* (i.e., this Decree)? | Only the boilerplate phrase `"중대재해 처벌 등에 관한 법률 시행령 일부를 다음과 같이 개정한다"`. Otherwise the body of each amending 부칙 is dominated by the *other* law's name (도서관법 / 화학물질관리법 / etc.). | Decree XML lines 820, 847, 874, 901, 928 |
| Is the high-value content in the Act 부칙 also reachable via metadata? | Partially. `legal_documents.effective_date` carries the headline 시행일 (2022-01-27). The phased-enforcement carve-out (50인 미만 → 공포 후 3년) is **only** in the 부칙 prose. | ERD draft `legal_documents` block; Act XML line 662 |

## Decision

`supplementary_provisions` is **not** a chunk source in Phase 1.

The chunks DDL from ADR-003 stays as-is: no `provision_id BIGINT`
FK column, no CHECK-constraint branch, no `source_type` generated
branch for 부칙. Phase-1 chunk sources are exactly `structure_nodes`
and `annexes`.

`supplementary_provisions` rows are still ingested, persisted, and
queryable via direct SQL — they are simply not surfaced through the
hybrid retrieval pipeline (BM25 + vector + RRF + reranker).

## Options considered

| Option | Shape | Verdict |
|--------|-------|---------|
| A | Index every 부칙단위 row as a chunk source | rejected — see "vs. A" |
| B | Selective: index 제정 부칙 only, distinguish via a `kind` column or first-line regex | rejected (closest competitor) — see "vs. B" |
| **C** | **Not a chunk source in Phase 1; revisit on explicit triggers** | **accepted** |

### Why C over A — the noise profile of indexing all rows is materially bad

1. **Cross-law spurious matches.** Every 일부개정 부칙 in the Decree
   is structurally a "다른 법령의 개정" — its body text is dominated
   by *another law's name* (도서관법, 화학물질관리법, 관광진흥법,
   기후에너지환경부 직제, 고용노동부 직제). A user query about
   "도서관법" hits 중대재해처벌법 시행령's 부칙 because the 부칙
   textually contains "도서관법". This is exactly the retrieval-poison
   pattern ADR-001 cited when excluding `forms` from the index.

2. **Near-duplicate chunks across rows.** 부칙키 `2025100135804` and
   `2025100135805` make the *same* textual change ("환경부장관" →
   "기후에너지환경부장관") because the same revision was issued by
   two different regulatory packages on the same day. Indexing both
   creates near-duplicate top-k results that no reranker handles for
   free.

3. **Within-row mixed signal.** Even the Act's 제정 부칙 — the
   highest-value 부칙 row in Phase 1 — mixes high-signal 시행일
   content (50인 미만 carve-out) with low-signal cross-law content
   (제2조 amends 법원조직법). Indexing the row as one chunk
   guarantees the 법원조직법 mention surfaces on 법원조직법 queries.
   Cleanly separating them requires the deferred 부칙내용 parsing
   decision; without that, indexing the row indexes both halves.

4. **"Reranker handles it" is hand-wave.** bge-reranker-v2-m3 is
   strong but not magic. The 35804/35805 near-duplicate problem is a
   hard case for any cross-encoder reranker, and RRF+rerank quality
   degrades when the candidate set is salted with off-topic
   cross-references rather than topic-relevant alternatives.

### Why C over B — the closest competitor

Option B (index only 제정 부칙) is the strongest counter to C, because
it captures the high-value content (Act 부칙's 시행일 + carve-out)
while excluding the worst noise (amending 부칙). The reasons it still
loses to C in Phase 1:

1. **B requires the deferred `kind` column to land *now*.** ADR-004
   explicitly deferred the 제정-vs-일부개정 distinction. B forces
   that decision. The kind value is observable in the data (the
   parenthetical in 부칙내용's first line, e.g., `부칙(도서관법
   시행령) <…>` vs `부칙 <…>`; or 부칙공포번호 cross-checked against
   the law's enactment announcement number) but the choice between
   parser-time inference and explicit column is non-trivial. C
   defers it; B can't.

2. **The within-row mixed-signal problem survives B.** B excludes
   amending 부칙 entirely, but the Act's 제정 부칙 still contains
   the 다른 법률의 개정 → 법원조직법 sub-clause. Without 부칙내용
   parsing (also deferred), B indexes that mention along with the
   high-signal 시행일.

3. **Phase-1 eval set distribution.** The Phase-1 evaluation queries
   will be dominated by article-level retrieval (substantive
   obligations, definitions, penalties under 중대재해처벌법) — the
   target users are practitioners, and practitioners hit 조문 first.
   "이 법은 50인 미만 사업장에 언제부터 적용되나?" is a real query,
   but it is one query *type* among many. Indexing it now without an
   eval baseline that demonstrates a need is the same anti-pattern
   `phase-1-progress.md §10` flags for LLM routing — "routing
   without measurement."

4. **The compound deferral is too much.** B couples three decisions
   into one ADR: chunk-source status (this ADR), kind-column
   placement (ADR-004 deferred), and 부칙내용 parsing (ADR-004
   deferred). C makes the cleanest single decision and leaves the
   other two cleanly deferrable.

### Steelman of B that I considered and reject

> "The 50인 미만 carve-out IS substantive law. Excluding it from
> semantic search degrades retrieval correctness for queries that
> hit it. That's a real cost — the user *can't find* the answer
> through the search interface even though we have the data."

Granted. But (i) the carve-out is reachable via document-level
navigation: a user querying "중대재해처벌법" finds the Act, and
부칙 is part of the Act page. The retrieval gap is "you can't get
straight to the carve-out from a free-text query"; the gap is not
"the answer is invisible." (ii) Every Phase-1 retrieval system has
*some* false negatives by construction; the empirical question is
which false negatives matter most in the eval distribution. Phase-1
evals will tell us if 부칙 carve-out queries are common enough to
drive the schema change. (iii) Adding 부칙 indexing later is
strictly additive (new column, new CHECK branch, new source_type
branch) — no breaking migration. The reverse direction (removing
부칙 chunks if they underperform) is also non-breaking but
operationally noisier (drop chunks rows + remove FK + simplify
CHECK + simplify generated expression).

The strongest version of this counter-argument is "you should still
land B because retrieval-correctness gaps are visible to users
*before* evals are run, and a portfolio reviewer reading 'we excluded
부칙 carve-outs' will read it as a gap." My answer: a documented,
evaluation-aware exclusion with explicit revisit triggers reads
better in a portfolio context than an under-argued inclusion that
ships near-duplicate cross-law noise.

## Trade-offs accepted

- **Phase-1 retrieval cannot answer carve-out / phased-enforcement
  queries via free-text search.** Practitioners who query "50인 미만
  사업장 적용 시기" will not get a chunk-level hit. They will need
  to navigate to the Act page and read 부칙. This is a real cost,
  and it is the dominant reason this ADR is non-obvious.

- **The eval baseline measured under this ADR will not see the
  noise problems described in "vs. A" / "vs. B".** That is the
  intended trade — we are deliberately not running the experiment
  yet. If Phase 2's eval set later motivates indexing 부칙, we will
  have a baseline to compare against.

- **`supplementary_provisions` is "indexed" in the SQL sense but
  not in the retrieval sense.** This split (persisted but not
  search-surfaced) is unfamiliar to readers expecting a single
  pipeline. Documented here and in ADR-004; needs a one-line note
  in any future README section that lists chunk sources.

## Revisit triggers (explicit conditions under which to overturn this ADR)

This ADR is deliberately reversible. Flip to chunk-source if **any**
of the following becomes true:

1. **Phase-2 eval set** includes ≥ 5% effective-date / phased-
   enforcement / amendment-history queries, AND the recall on those
   queries against `chunks` (no 부칙 indexing) is materially below
   the recall on body-content queries.
2. **Real user logs** (post-launch) show a measurable rate of
   queries that match 부칙 prose patterns ("언제부터 시행", "적용
   대상", "공포 후 N년") with low click-through on body-only
   results.
3. **Phase-2 scope expansion** to other statutes whose 부칙 is
   structurally richer than 중대재해처벌법's (e.g., older statutes
   with substantive transitional provisions in 부칙). Current
   Phase-1 decision is grounded in this specific statute's 부칙
   profile; a different profile would update the empirical basis.

When triggered, the migration is additive (per ADR-003's
extension pattern) — covered in "Trade-offs accepted" #3 above.

## What is checked vs. what is still open

**Checked (this ADR):**

- Content profile of all 6 Decree 부칙단위 rows (1 제정 + 5
  일부개정), including the cross-law mention pattern and the
  35804/35805 near-duplicate.
- Content profile of the Act's 1 부칙단위 row (제정), including
  the within-row mixed-signal pattern (시행일 + 다른 법률의 개정).
- Reachability of the headline 시행일 via `legal_documents.
  effective_date` (yes); reachability of the carve-out
  (no — only via 부칙 prose).

**Still open (deferred to future ADRs / measurement):**

- Quantitative noise impact on retrieval. Can only be measured
  once the Phase-1 eval baseline exists. Until then, the noise
  argument is qualitative (cross-law mentions + near-duplicate
  rows are described, not benchmarked).
- Whether the kind distinction (제정 vs 일부개정) needs an
  explicit column. Stays deferred; only becomes live if a future
  ADR overturns this one toward Option B.
- 부칙내용 internal parsing (제N조 sub-structure). Stays deferred;
  only becomes live if a future ADR overturns this one toward
  fine-grained chunking inside a 부칙단위 row.

## Consequences

- ADR-003's chunks DDL stays unchanged. `structure_node_id` and
  `annex_id` remain the only Phase-1 statute FK columns; the
  CHECK constraint stays at `(structure_node_id IS NOT NULL)::int +
  (annex_id IS NOT NULL)::int = 1`; the generated `source_type`
  expression has no `'statute_provision'` branch.
- The Phase-1 ingestion script branches on `<조문>` / `<별표>` /
  `<부칙>` and writes 부칙 rows to `supplementary_provisions`
  without producing any chunks rows from them.
- Phase-1 evaluation harness reports retrieval metrics over a
  candidate pool that does not include 부칙. Carve-out / phased-
  enforcement queries appear in the eval set only if they can be
  answered from `structure_nodes` or `annexes` (almost certainly
  not).
- ERD draft acknowledges the decision in the
  `supplementary_provisions` block ("not a chunk source in Phase
  1; see ADR-005") on acceptance.

## References

- `docs/decisions/ADR-001-split-annexes-and-forms.md` — precedent
  for excluding a persisted source from the chunks index on
  retrieval-quality grounds (`forms`)
- `docs/decisions/ADR-003-chunks-fk-shape.md` — chunks DDL whose
  Phase-1 column list this ADR confirms as complete
- `docs/decisions/ADR-004-supplementary-provisions-placement.md` —
  upstream placement decision; this ADR closes its deferred Q1
- `docs/api-samples/law-228817-중대재해처벌법.xml` — Act 부칙 (1
  row; 시행일 carve-out evidence; within-row mixed-signal evidence)
- `docs/api-samples/law-277417-중대재해처벌법시행령.xml` — Decree
  부칙 (6 rows; cross-law mention pattern; 35804/35805 near-
  duplicate)
- `phase-1-progress.md` §10 — "routing without measurement" anti-
  pattern, by analogy
