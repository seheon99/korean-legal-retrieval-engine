# ADR-018 — Annex content de-layout normalization

- **Status**: Accepted
- **Date**: 2026-05-05
- **Context layer**: Statute (성문규범) ingestion pipeline —
  annex `content_text` normalization
- **Supersedes / amends**:
  - **ADR-014 (Accepted)** — replaces the earlier rule that preserved
    internal `<별표내용>` spaces, indentation, blank lines, and table-like
    layout text after outer stripping.
- **Depends on / aligned with**:
  - **ADR-011 (Accepted)** — raw XML remains the fidelity source under
    `data/raw/`.
  - **ADR-016 / ADR-017 (Accepted)** — rendered PDF binaries remain the
    durable visual fallback under `data/annexes/`.
- **Resolves**:
  - Whether `annexes.content_text` should preserve upstream fixed-width
    rendered layout.
  - How to prevent legal terms split across layout lines from becoming
    unsearchable.
  - Whether `content_hash` follows raw layout text or normalized semantic
    text.
- **Out of scope (not decided here)**:
  1. Full table reconstruction from annex PDFs/HWP.
  2. OCR.
  3. Korean BM25 tokenizer design for ordinary spacing variants beyond
     layout wraps.
  4. Adding a separate `search_text` column.
  5. Choosing the final production Korean tokenizer library.

## Context

The Phase-1 Decree annex XML stores `<별표내용>` as fixed-width rendered
layout lines. The raw XML splits ordinary words across CDATA lines with
blank layout rows between them:

```text
3. 교량의 “연장”이란 교량 양측 교대의 흉벽 사이를 교량 중심선에 따라 측정한 거

리를 말한다.
```

ADR-014 preserved internal layout. The resulting `annexes.content_text`
contains `거` and `리` as separate lines, so a BM25 query for `거리`
cannot match the annex content.

The `복부` / `산통(産痛)` split in annex 1 exposed the same retrieval
failure mode, but the correct surface form may be `복부 산통` rather than
`복부산통`. ADR-018 does not decide that medical spacing question. Use
unambiguous hard-wrap repairs as the acceptance target.

This is not an isolated cosmetic issue. The same annex also contains
layout wraps such as:

- `노출되` + `어`
- `청` + `색증`
- `유해인` + `자`
- `건강장` + `해`
- `심부체온상승` + `을`
- `거` + `리`
- `포` + `함한`

Raw layout preservation is therefore the wrong default for
`annexes.content_text`. Raw XML and retained PDFs already cover fidelity.
`content_text` should be the semantic text used by ingestion and retrieval.

## Decision

Normalize annex `<별표내용>` into de-layouted semantic text before storing
it in `annexes.content_text`.

`annexes.content_text` is not a byte-faithful rendering of the upstream
layout. It is the parser-owned semantic text surface for downstream
chunking and retrieval. The canonical fidelity sources remain:

- raw XML under `data/raw/{law_id}/{mst}.xml`
- retained PDF under `data/annexes/{law_id}/{mst}/{annex_key}/...pdf`

For `<별표내용>`:

1. Concatenate the element's text and descendants in XML order.
2. Normalize line endings to LF (`\n`): CRLF and bare CR become LF.
3. Split into lines.
4. Strip leading/trailing whitespace from each line.
5. Drop empty or whitespace-only layout lines.
6. Classify each adjacent non-empty line boundary into one of four
   decisions:

   ```text
   JOIN_NO_SPACE
   JOIN_WITH_SPACE
   KEEP_BLOCK_BREAK
   LOW_CONFIDENCE_REVIEW
   ```

### Structural boundaries

Structural boundaries are rule-based and run before tokenizer scoring.
Return `KEEP_BLOCK_BREAK` before an obvious annex block start:

- rendered annex header, e.g. `■ ... [별표 1]`
- numbered item, e.g. `1. ...`
- Korean letter item, e.g. `가. ...`
- note marker, e.g. `비고`

Do not send structural boundaries to tokenizer scoring.

### Continuation boundaries

For every non-structural boundary, generate two local candidates:

```text
A = prev_line + next_line
B = prev_line + " " + next_line
```

Use a Korean tokenizer / morphological analyzer as a scoring function for
that local boundary, not as a full text normalizer.

Decision rule:

```text
if structural boundary:
    KEEP_BLOCK_BREAK
elif tokenizer strongly prefers A:
    JOIN_NO_SPACE
elif tokenizer strongly prefers B:
    JOIN_WITH_SPACE
else:
    LOW_CONFIDENCE_REVIEW
```

Decision semantics:

| Decision | Meaning |
|----------|---------|
| `JOIN_NO_SPACE` | Merge `prev_line` and `next_line` without inserting a space |
| `JOIN_WITH_SPACE` | Merge with one ASCII space between the lines |
| `KEEP_BLOCK_BREAK` | Preserve a logical block break between the lines |
| `LOW_CONFIDENCE_REVIEW` | Do not auto-normalize; require reviewed boundary decision |

The concrete tokenizer library and scoring thresholds are implementation
details for the first normalizer spike. They must be recorded before the
ADR is implemented permanently, but ADR-018 decides the abstraction:
line-boundary candidate scoring, not hardcoded suffix lists.

Low-confidence boundaries must not be silently normalized. In Phase 1,
they require a manually reviewed decision captured in the repository so
re-ingest remains reproducible. In later phases, accumulated approved
boundaries can become a dataset for higher-confidence automatic decisions.

After all boundary decisions are applied, join logical blocks with a
single LF and strip only the final full string's outer whitespace.

`content_hash` remains SHA-256 of the stored `content_text` UTF-8 bytes.
Because `content_text` changes while raw XML does not, existing
Phase-1 annex rows need an explicit child-row refresh so affected
annex `content_hash` values are updated.

## Required examples

The first Phase-1 Decree annex must contain these normalized substrings:

```text
노출되어 발생한 중추신경계장해
유기화합물에 노출되어
발생한 렙토스피라증
심부체온상승을 동반하는 열사병
```

The third Phase-1 Decree annex must contain these normalized substrings:

```text
교량 중심선에 따라 측정한 거리를 말한다
각 본체 구간과 하나의 구조로 연결된 구간을 포함한 거리를 말한다
```

It must not preserve the layout-only split:

```text
거

리
```

The `복부` / `산통(産痛)` boundary must not be used as an automatic
acceptance target. A tokenizer may prefer `복부 산통(産痛)` over
`복부산통(産痛)`, but this is a semantic spacing decision. In Phase 1,
that boundary is manual-review material unless a chosen tokenizer and
reviewed decision clearly classify it.

## Options considered

| Option | Verdict |
|--------|---------|
| A. Tokenizer-assisted local boundary classification with rule-based structural boundaries and manual review for low confidence cases | **recommended** — fixes layout wraps without pretending to solve full Korean spacing |
| B. Preserve ADR-014 layout exactly and defer all repair to chunk generation | rejected — leaves the source row itself hostile to search and chunking |
| C. Add `annexes.search_text` beside `content_text` | rejected for Phase 1 — adds schema surface before chunks exist |
| D. Remove all whitespace from Korean text globally | rejected — over-corrects and destroys readable semantic text |
| E. Use PDF/HWP extraction as the primary annex text source | rejected — XML already provides text; binaries are fallback evidence, not the primary parser source |
| F. Hardcode Korean suffix / particle join rules as the primary algorithm | rejected — brittle, grows into rule explosion, and cannot express confidence |

## Consequences

- Annex text becomes suitable for chunking and lexical retrieval.
- `annexes.content_hash` changes for existing annex rows after re-ingest.
- Raw layout can still be audited through retained raw XML and PDF files.
- Phase 1 needs a reviewed boundary-decision artifact or equivalent tests
  so normalization is reproducible.
- A concrete tokenizer choice remains to be made during implementation.
- This does not solve every Korean spacing variant. The BM25 layer still
  needs Korean-aware tokenization or whitespace-insensitive matching for
  normal spacing differences, but layout-induced term splitting is removed
  at the source.

## Implementation note

The current ingest image has no Korean tokenizer dependency. The Phase-1
implementation therefore uses a reviewed deterministic boundary classifier
as the temporary manual-only scoring substitute allowed by this ADR.

The production tokenizer choice remains a follow-up before this normalizer
is generalized beyond the Phase-1 corpus.

## Implementation requirements

1. Choose a Korean tokenizer / morphological analyzer for boundary
   scoring, or explicitly document a temporary Phase-1 manual-only scoring
   substitute.
2. Replace `_normalized_element_text()` usage for `<별표내용>` with an
   annex-specific de-layout normalizer.
3. Generate and review boundary decisions for the Phase-1 annexes.
4. Capture reviewed low-confidence decisions in the repository.
5. Add parser tests for the required Phase-1 substrings.
6. Refresh existing annex child rows or re-run ingestion from a clean DB
   against the Compose database.
7. Verify `annexes.content_text` no longer contains the `거` / `리`
   layout split and does contain `거리를 말한다`.
