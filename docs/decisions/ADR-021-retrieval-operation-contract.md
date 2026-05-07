# ADR-021 — Retrieval operation contract is legal-intent-first

- **Status**: Accepted
- **Date**: 2026-05-07
- **Context layer**: Retrieval API contract, agent-facing operation model
- **Depends on / aligned with**:
  - **ADR-003** — `chunks` is the unified search index with real source
    FKs.
  - **ADR-013** — legal effectiveness is computed from temporal predicates,
    not from `is_head` alone.
  - **ADR-019** — Phase 1 builds the SAPA + OSH statutory hybrid baseline.
  - **ADR-020** — canonical statute source rows come from effective-date
    specific `eflaw` XML.
- **Out of scope**:
  1. Exact HTTP route names.
  2. SDK method names.
  3. Final chunk schema DDL.
  4. Presentation-layer concerns: SDK ergonomics, transport encoding, and
     any human-facing UI.
  5. Generation or answer synthesis.
  6. Implementing downstream reasoning, routing, or orchestration stages in
     Phase 1.

## Context

The project is a retrieval engine consumed primarily by an AI agent, not a
human-facing search UI.

That changes the first public contract. The consumer should express legal
intent:

- resolve this known legal citation
- retrieve evidence for this legal concept query

It should not be forced to choose implementation knobs:

- BM25 vs semantic retrieval
- raw `top_k`
- reranker settings
- citation-required flags
- low-level source-type filters

Those knobs are retrieval-engine internals. Exposing them first would leak
implementation mechanics into the agent contract and make downstream agents
responsible for choices the retrieval engine is supposed to own.

The engine also has two materially different retrieval problems:

1. exact legal identity resolution
2. relevance-ranked evidence retrieval

Treating both as "search" would collapse an authority problem into a
similarity problem. That is wrong for law.

## Decision

Expose two primary retrieval operation classes.

### 1. Deterministic retrieval

Deterministic retrieval resolves known legal citations or identifiers to
the exact effective legal provision.

Examples:

```text
형법 제1조 제1항
산업안전보건법 제2조 제1호
중대재해 처벌 등에 관한 법률 시행령 별표 1
```

This operation is identity-based, not similarity-based.

The final result must be selected by structured source identity:

- law identity
- document version / effective-date slice
- hierarchy node or annex identity
- temporal predicate for the requested legal-effective date

Deterministic retrieval is not bounded by the Phase-1 chunks index
(ADR-003). Identity resolution covers any source-table row a citation can
target:

- `structure_nodes` — articles, paragraphs, items, sub-items
- `annexes` — 별표 / 별지 attachments addressed as an annex unit
- `supplementary_provisions` — 부칙 articles
- `forms` — 시행규칙 별지 forms addressed by form key
- `annex_attachments`, `form_attachments` — when the citation targets a
  specific binary attachment

For non-chunkable source kinds, the result envelope's `source table and
source row ID` field carries the resolved row, and the hierarchy path may
bottom out at the non-chunkable source row instead of a chunk-source row.
Retrieval at the chunks index level remains restricted to ADR-003's
Phase-1 source FKs.

BM25, semantic retrieval, or fuzzy matching may be used only as fallback
normalization when the input citation is incomplete, abbreviated, or
orthographically noisy. Similarity search is not the authority for the
final result.

If the engine cannot resolve the citation to a unique legal identity, it
must return an ambiguity or unresolved result rather than silently choosing
the nearest semantic match.

### 2. Hybrid evidence retrieval

Hybrid evidence retrieval searches for legally relevant evidence when the
consumer provides a concept-level legal query.

Example:

```text
중대재해처벌법 경영책임자 안전보건 확보의무 처벌
```

This operation uses retrieval internals such as:

- lexical retrieval
- semantic retrieval
- fusion
- reranking
- structured filtering
- provenance packaging

The operation does not generate an answer. It returns citation-ready legal
evidence objects that a downstream agent may use for reasoning or answer
generation.

Hybrid evidence retrieval may rank competing evidence, but it must not
pretend that high similarity alone establishes legal identity or legal
effectiveness. Temporal and source-identity constraints remain structured
filters.

## Agent-facing contract rule

The first public contract is legal-intent-first.

The agent should request operations like:

```text
resolve known citation under an effective-date policy
retrieve evidence for a legal concept under an effective-date policy
```

The agent should not select:

- BM25 vs semantic retrieval
- raw candidate `top_k`
- reranker model or threshold
- citation-required mode
- low-level source-type inclusion/exclusion
- RRF parameters

Those settings may exist as internal configuration, diagnostics, test
harness inputs, or admin-only controls. They are not the normal public
contract for the primary AI-agent consumer.

Legal-intent parameters are still valid public inputs when they change the
meaning of the legal request rather than the mechanics of retrieval.
Examples:

- effective-as-of date
- current-law vs explicit future-law mode
- citation string or known source identifier
- concept query
- jurisdiction / corpus boundary when multiple corpora exist later

Effective-date mode follows ADR-013:

- effective-as-of / current-law mode uses the temporal predicate
  `effective_at <= requested_at < superseded_at`, with `superseded_at IS
  NULL` treated as open-ended.
- head / explicit future-law mode may target `is_head = TRUE` or a future
  `effective_at`, but it must be requested explicitly and must not be used
  as the default current-law predicate.

## Operation routing

The agent should not be responsible for choosing deterministic retrieval
versus hybrid evidence retrieval for ambiguous or mixed inputs.

The engine should perform operation routing internally from the legal-intent
request.

Input classes:

1. **Known citation / identifier**
   - Example: `산업안전보건법 제4조`
   - Route to deterministic retrieval.

2. **Concept-level evidence query**
   - Example: `중대재해처벌법 경영책임자 안전보건 확보의무 처벌`
   - Route to hybrid evidence retrieval.

3. **Mixed citation + concept query**
   - Example: `산업안전보건법 제4조의 처벌 범위`
   - First run deterministic retrieval to anchor the cited legal unit.
   - Then run hybrid evidence retrieval constrained or boosted by that
     anchor, depending on the implementation design.
   - Return both the resolved anchor and the evidence results, or return an
     ambiguity / unresolved envelope if the anchor cannot be resolved.
   - The composition mode (e.g. `anchor-filter` for hard restriction to
     the anchor's hierarchy, `anchor-boost` for soft re-ranking) must be
     reported in the routing diagnostics so evaluation can distinguish
     the two without reverse-engineering rank lists.

4. **Unclassifiable input**
   - Return a typed unresolved or unsupported-intent response with parsed
     fragments and reason code.

**Phase-1 corpus boundary.** ADR-019 freezes Phase-1 corpus to the SAPA
and OSH statutory families. Requests that resolve to a `law_id` outside
that corpus must return an `unresolved` envelope with reason code
`out-of-corpus`, even when upstream `target=law` discovery would otherwise
succeed. The corpus check runs during routing and applies to all input
classes above.

This preserves the legal-intent-first contract: the agent may state the
legal task, but the engine owns the retrieval-operation selection and
composition. Internal routing decisions must be exposed as diagnostics for
evaluation and debugging, not as required public knobs.

## Future composition extensibility

The retrieval operation contract should remain composable with future
downstream stages without requiring the first public agent contract to
expose raw retrieval knobs.

This means Phase-1 design should preserve three generic properties:

1. **Operation-level composition**
   - Downstream stages may later consume deterministic retrieval results,
     hybrid evidence results, or both.
   - The public contract should remain legal-intent-first even if additional
     stages are composed behind or after an operation.

2. **Evidence-object compatibility**
   - Evidence results must be structured enough for machine consumers to
     consume directly.
   - Citation, provenance, source identity, effective-date metadata, and
     hierarchy context are therefore required machine fields, not display
     decoration.

3. **Diagnostics without API leakage**
   - Internal retrieval traces, candidate scores, fusion ranks, and reranker
     scores may be retained for evaluation and future downstream features
     in the fixed `diagnostics` block defined under the result envelope.
   - These diagnostics must not become mandatory public knobs for the
     primary AI-agent consumer.

Future composition does not change the Phase-1 execution order. The first
baseline still proves deterministic retrieval and hybrid evidence retrieval
before adding reasoning, routing, orchestration, or other downstream stages.

## Required result envelope

Every valid result from either operation class must include:

- citation
- provenance
- source identity
- effective-date metadata
- hierarchy context

For Phase 1 statute results, this means at minimum:

- canonical citation text
- canonical document version identity: `(law_id, mst, effective_date)` per
  ADR-020. `mst` alone is not the local version identity; the three fields
  together form one key.
- temporal effectiveness fields, derived from the version row, not from
  identity:
  - `effective_at`
  - `superseded_at`
  - `is_head` — ingestion-lineage flag per ADR-013, not legal
    effectiveness. Legal effectiveness comes from the `effective_at` /
    `superseded_at` predicate, not from `is_head`.
- `source_url` — non-OC API identity including `target=eflaw`, `MST`, and
  `efYd` per ADR-020. The agent should not reconstruct this URL from the
  version identity fields.
- source row `content_hash`
- source table and source row ID
- hierarchy path, such as law title -> chapter/section/article/paragraph
  or law title -> annex key/title

Hybrid evidence results additionally need rank/score diagnostics for
evaluation and debugging, but those diagnostics do not replace citation or
provenance metadata.

Hash rule:

- `source_content_hash` must refer to the canonical source row content hash.
  In Phase 1, this is the existing source-table `content_hash` for the
  cited `structure_nodes`, `annexes`, or other source row.
- Future chunk or evidence-object hashes may be returned as additional
  fields, but they must not replace `source_content_hash`.
- Cache keys and eval rows should key against source identity plus
  `source_content_hash`; chunk/evidence hashes are derived-object
  diagnostics unless a later ADR promotes them.

## Evidence-list shape

Hybrid evidence retrieval returns a list. The Phase-1 contract for that
list is:

- bounded length, engine-chosen and not a public knob; the engine returns
  enough evidence for downstream reasoning without exposing `top_k`.
- engine-ranked descending by the engine's internal scoring; tie-breaking
  is engine-chosen.
- deduplicated to one evidence object per `(source table, source row,
  source_content_hash)`. When ADR-003's 1:N chunking produces multiple
  chunks from the same source row, those chunks are rolled up into one
  evidence object with chunk-level diagnostics, not returned as siblings.

This makes evidence objects safely keyable by source identity plus
`source_content_hash` for caches and eval rows.

Deterministic retrieval returns one resolved result, one ambiguity
candidate list, or one unresolved envelope. It does not return a ranked
evidence list and is not subject to this section.

## Diagnostics block

When the engine returns retrieval-internal information — operation routing
decision, fallback-normalization flags, candidate scores, fusion ranks,
reranker scores, mixed-input composition mode — it returns it as an
explicit `diagnostics` block in the envelope. The block is:

- non-authoritative; consumers must not rely on it for legal correctness.
- positionally fixed in the envelope so evaluation tooling can read it
  without per-call schema discovery.
- additive; exact field schema is deferred but the block's existence and
  location are part of the contract.

`diagnostics` is the home for every non-authoritative signal the engine
chooses to expose. It is not a public retrieval knob.

## Ambiguity and unresolved envelope

Deterministic retrieval may fail to resolve a unique legal identity. In
that case, the operation must return a typed non-success envelope rather
than a best-effort semantic match.

The non-success envelope should include:

- status, such as `ambiguous` or `unresolved`
- normalized input fragments the engine was able to parse
- reason code, such as unknown law title, missing hierarchy unit,
  effective-date conflict, multiple candidate provisions, or out-of-corpus
  source
- candidate list when candidates exist, each carrying the same citation,
  provenance, source identity, effective-date metadata, and hierarchy
  context available for that candidate
- confidence or match diagnostics for candidate-generation only, explicitly
  marked as non-authoritative

If no plausible legal identity exists, return `unresolved` with an empty
candidate list and the parsed fragments / reason code. If multiple plausible
identities exist, return `ambiguous` with candidates and require the
consumer to disambiguate or retry with a more specific request.

## Options considered

| Option | Verdict |
|--------|---------|
| A. One generic `search` operation with many knobs | rejected — exposes retrieval mechanics instead of legal intent |
| B. Hybrid retrieval only, using similarity for citations too | rejected — turns identity resolution into a relevance problem |
| C. Deterministic citation resolver only | rejected — cannot answer concept-level evidence discovery needs |
| D. Two legal-intent operations: deterministic retrieval and hybrid evidence retrieval | recommended — matches legal semantics and keeps retrieval mechanics inside the engine |

## Consequences

- The retrieval layer needs separate evaluation tracks:
  - deterministic citation-resolution accuracy
  - hybrid evidence retrieval Recall@K / MRR
- The `chunks` migration and retrieval code should not be the only retrieval
  surface. Deterministic retrieval must be able to resolve source identities
  directly from source tables and hierarchy keys.
- The first public API should expose operations, not retrieval primitives.
- Internal retrieval primitives still need testability and diagnostics, but
  they should be behind the operation layer.
- Provenance packaging is not optional. A result without citation,
  source identity, temporal metadata, and hierarchy context is not a valid
  legal retrieval result.

## Acceptance criteria

- Retrieval design distinguishes deterministic citation resolution from
  hybrid evidence retrieval.
- Citation resolution does not use BM25/vector similarity as final
  authority.
- Hybrid evidence retrieval returns evidence objects, not generated answers.
- Public operation inputs express legal intent, not low-level retrieval
  knobs.
- Every valid result carries citation, provenance, source identity,
  effective-date metadata, and hierarchy context.
- Phase-1 retrieval design preserves generic downstream composition without
  implementing future stages or exposing their internal knobs.
- The engine owns routing between deterministic retrieval, hybrid evidence
  retrieval, and mixed citation-plus-concept composition.
- Deterministic retrieval that cannot uniquely resolve a citation returns
  the typed ambiguity / unresolved envelope (status, parsed fragments,
  reason code, candidate list when available, non-authoritative
  diagnostics) rather than a best-effort semantic match.
- Mixed citation-plus-concept inputs return both the resolved anchor and
  the evidence results, or a typed unresolved envelope when the anchor
  cannot be resolved; the composition mode is reported in routing
  diagnostics.
- Evaluation harness exists for both operation tracks: deterministic
  citation-resolution accuracy, and hybrid evidence Recall@K / MRR per
  ADR-019.
