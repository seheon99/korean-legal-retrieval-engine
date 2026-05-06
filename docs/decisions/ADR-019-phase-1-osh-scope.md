# ADR-019 — Phase 1 scope expansion: add 산업안전보건법 full family

- **Status**: Accepted
- **Date**: 2026-05-06
- **Context layer**: Phase-1 scope, statute ingestion, retrieval baseline
- **Amends**:
  - **Project operating manual / Phase-1 walking skeleton** — replaces
    "single statute end-to-end before generalization" with a two-family
    statute scope.
  - **ADR-010** — Phase-1 statute schema remains frozen, but the empirical
    corpus used to validate it expands.
  - **ADR-013** — makes head/effective distinction operationally urgent
    because OSH has future-effective slices.
  - **ADR-014 / ADR-017** — annex ingestion and binary retention now need
    to survive a larger statute family.
- **Depends on / aligned with**:
  - **ADR-003** — chunks use split FK columns with real FKs.
  - **ADR-005** — `supplementary_provisions` is not a Phase-1 chunk source.
  - **ADR-015** — schema changes ship as ordered SQL migrations.
  - **ADR-018** — annex `content_text` is semantic text for retrieval.
- **Out of scope**:
  1. Judicial / interpretive / academic / practical-source ingestion.
  2. Making `forms` a chunk source.
  3. Making `supplementary_provisions` a chunk source.
  4. Final production deployment / serving API.

## Context

The original Phase-1 walking skeleton scoped the project to
`중대재해 처벌 등에 관한 법률` and its Enforcement Decree. That was a good
schema-freeze path, but it is now too narrow for retrieval evaluation.

`중대재해처벌법` repeatedly delegates or cross-references
`산업안전보건법`. Examples already present in the retained SAPA XML include:

- SAPA Act definition of `중대산업재해` via `산업안전보건법` Article 2.
- SAPA Decree requirements for safety/health personnel, risk assessment,
  worker-opinion procedures, and education institutions via
  `산업안전보건법`.
- SAPA Decree annex occupational-disease references to OSH health-check and
  working-environment measurement regimes.

A retrieval baseline that cannot retrieve the referenced OSH provisions is
not a credible legal retrieval baseline for this topic. It measures
article lookup inside one statute family, not cross-statute legal retrieval.

law.go.kr evidence gathered on 2026-05-06 also shows that OSH has a richer
shape than SAPA:

- `산업안전보건법` has current and future-effective slices, including
  future-effective pages for 2026-06-01 and 2026-08-01.
- `산업안전보건법 시행령` has a current page showing
  `[시행 2026. 3. 24.]`.
- `산업안전보건법 시행규칙` has a current page showing
  `[시행 2026. 1. 1.]` and exposes a `서식` section.

This makes the old single-statute assumption actively harmful. The
strongest Phase-1 scope is still narrow, but the unit should be the
SAPA + OSH statutory neighborhood, not SAPA alone.

## Decision

Expand Phase 1 statute scope to two full statutory families:

1. `중대재해 처벌 등에 관한 법률`
   - Act
   - Enforcement Decree
   - no known Enforcement Rule in the current SAPA corpus
2. `산업안전보건법`
   - Act
   - Enforcement Decree
   - Enforcement Rule

For OSH, ingest both:

- the legally effective slice as of `2026-05-06`
- head / future-effective slices returned by law.go.kr discovery

Retrieval and evaluation default to the legally effective slice as of
`2026-05-06`. Head/future rows are retained so future-effective queries can
be tested explicitly later, but they must not silently contaminate
current-law answers.

The first retrieval baseline should be hybrid immediately:

```text
BM25 + vector candidates -> RRF -> bge-reranker-v2-m3
```

The embedding model is not frozen by this ADR. Compare `bge-m3` and KURE
on the same seed eval set. Freeze the embedding model and vector dimension
only after that comparison.

`supplementary_provisions` and `forms` remain persistence-only in Phase 1:

- persist them because OSH full-family ingestion needs complete source
  coverage
- do not emit chunks from them
- do not add `provision_id` or `form_id` to `chunks`

## Implementation order

1. **API discovery before code changes**
   - Use `lawSearch.do?target=law` and `lawSearch.do?target=eflaw` to
     discover OSH Act/Decree/Rule records.
   - Use `lawService.do?target=law` and `lawService.do?target=eflaw` to
     fetch retained raw XML candidates.
   - Record exact returned `law_id`, `mst`, `title`, `doc_type`,
     `effective_date`, and whether the fetch is head or effective-as-of.
   - If `target=eflaw` returns distinct XML for the same `(law_id, mst)`
     at different `efYd` values, stop and draft a raw-retention identity
     ADR before writing ingestion rows.

2. **Finish source-ingestion semantics**
   - Complete ADR-013 new-MST supersession behavior:
     `is_head`, `effective_at`, `superseded_at`, child-row supersession.
   - Implement `supplementary_provisions` parser and population.
   - Implement `forms` and `form_attachments` parser and population.
   - Keep form binaries provenance-only unless a separate ADR accepts form
     binary retention.

3. **Generalize parser only where OSH proves the need**
   - Verify 시행규칙 `법종구분` shape before relaxing ADR-006 logic.
   - Verify OSH heading keys before broadening the current
     `전문 -> level 2` mapping.
   - Verify annex/form key shapes before changing ADR-014 validation.

4. **Build retrieval baseline**
   - Add `chunks` per ADR-003, with only `structure_node_id` and
     `annex_id` as Phase-1 statute source FKs.
   - Generate chunks from effective-as-of source rows by default.
   - Build BM25, vector retrieval, RRF fusion, and reranking.
   - Compare `bge-m3` and KURE on identical eval queries before freezing
     model choice.

## Options considered

| Option | Verdict |
|--------|---------|
| A. Keep Phase 1 as SAPA only | rejected — misses the statute SAPA repeatedly cross-references |
| B. Add OSH Act only | rejected — too shallow; SAPA Decree references delegated OSH mechanisms that live below the Act |
| C. Add OSH Act + Decree, defer Rule | rejected — avoids forms risk but leaves the OSH family incomplete |
| D. Add OSH full family, effective-as-of only | rejected — avoids version complexity but fails to exercise ADR-013 head/effective separation |
| E. Add OSH full family, both head/future and effective-as-of slices | accepted — strongest Phase-1 retrieval/evaluation corpus while staying within 성문규범 |

## Consequences

- Phase 1 is no longer a single-statute walking skeleton. It is a
  two-family statute retrieval baseline.
- `forms` ingestion becomes live because OSH 시행규칙 has forms.
- ADR-013 supersession behavior becomes a blocker, not a later cleanup.
- The fetch script must stop being hard-coded to SAPA-only defaults.
- The evaluation set must include cross-statute questions that require OSH
  retrieval.
- Broad local `data/raw` ingestion is still not the goal. The target corpus
  is SAPA + OSH, not every local XML file.

## Acceptance criteria

- OSH Act, Decree, and Rule XML samples are retained and documented.
- Clean DB ingest succeeds for SAPA + OSH target corpus.
- Current-law retrieval defaults to as-of `2026-05-06` rows.
- Future/head rows are queryable only through explicit future/head mode.
- `supplementary_provisions` and `forms` persist but produce no chunks.
- First hybrid retrieval eval reports Recall@K and MRR for both `bge-m3`
  and KURE before model choice is frozen.

## References

- law.go.kr 국가법령정보센터:
  - `산업안전보건법` current/future search results observed on
    2026-05-06.
  - `산업안전보건법 시행령` page showing `[시행 2026. 3. 24.]`.
  - `산업안전보건법 시행규칙` page showing `[시행 2026. 1. 1.]` and
    a `서식` section.
- 법제처 DRF API guides:
  - `lawSearch.do?target=law`
  - `lawSearch.do?target=eflaw`
  - `lawService.do?target=law`
  - `lawService.do?target=eflaw`
- Existing retained SAPA XML:
  - `data/raw/013993/228817.xml`
  - `data/raw/014159/277417.xml`
