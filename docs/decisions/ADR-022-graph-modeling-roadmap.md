# ADR-022 — Graph modeling roadmap uses derived structural projection first

- **Status**: Accepted
- **Date**: 2026-05-07
- **Context layer**: Graph modeling roadmap, retrieval architecture,
  legal structure traversal
- **Depends on / aligned with**:
  - **ADR-003** — source ERDs remain separate while `chunks` provides a
    unified search index.
  - **ADR-009** — `legal_documents.parent_doc_id` stores Act-to-Decree /
    Act-to-Rule linkage in the ERD, and any future revisit of that linkage
    belongs there or in an ADR-009 follow-up.
  - **ADR-012** — `structure_nodes.node_key` and ordering rules provide
    stable structural anchors.
  - **ADR-013** — version rows, `effective_at`, `superseded_at`, and
    `is_head` keep graph projection version-aware.
  - **ADR-019** — Phase 1 is the SAPA + OSH statutory baseline.
  - **ADR-020** — canonical statute source rows come from `eflaw`
    effective-date slices.
  - **ADR-021** — retrieval operations require citation, provenance,
    source identity, effective-date metadata, and hierarchy context.
- **Out of scope**:
  1. Table design.
  2. Edge names.
  3. Indexing strategy.
  4. Migration strategy.
  5. Graph projection jobs.
  6. Reference extraction logic.
  7. Graph database selection.
  8. Legal semantic ontology design.

## Purpose

This ADR defines the roadmap direction for KLRE graph modeling.

It is not an implementation specification.

Detailed table design, edge naming, indexing, migration strategy, graph
projection jobs, and extraction logic must be handled separately by later
implementation ADRs or design documents.

This roadmap decides:

- why KLRE needs a graph layer
- how the graph relates to the current ERD
- what abstraction layers the graph should eventually support
- what Phase-1 graph work should and should not attempt to solve

## Decision

KLRE should evolve toward a graph-ready legal retrieval architecture.

The current ERD remains the Phase-1 canonical normalized storage model.
It should not be discarded or replaced by a graph-first model.

Introduce a graph projection layer on top of the current ERD.

For Phase 1, this projection is an identity and traversal contract over
existing ERD rows, not new physical graph infrastructure.

The graph is not a replacement for the ERD. The graph is a derived layer
used for:

- retrieval support
- legal structure traversal
- citation anchoring
- statute visualization
- future reference resolution
- future definition modeling
- future semantic reasoning

The graph must be projected from normalized legal storage, not maintained
as an independent source of truth.

Phase 1 should use the existing ERD traversal primitives already present in
the source layer, including `doc_id`, `node_key`, `parent_id`, `sort_key`,
and source-row identifiers for supplementary provisions, annexes, and
forms. A physical graph table, SQL view, materialized view, graph store, or
projection job is not part of this roadmap decision.

New graph storage or projection infrastructure requires a follow-up ADR
that justifies the concrete need, cost, schema, migration path, refresh
semantics, and cache/eval impact.

The core roadmap principle:

```text
First, make legal text structurally stable.
Then, resolve explicit references.
Then, model defined terms.
Only after that, attempt legal semantic modeling.
```

The most important Phase-1 graph decision:

```text
Build stable legal anchors before building legal intelligence.
```

## Multi-layer graph roadmap

KLRE should use a multi-layer graph roadmap:

```text
Layer 1: Structural Graph
Layer 2: Reference Graph
Layer 3: Definition Graph
Layer 4: Legal Semantic Graph
```

These layers are roadmap concepts.

They are not necessarily separate databases, separate tables, or strictly
sequential implementation units. They are abstraction levels that guide
future design.

## Relationship modeling policy

This roadmap does not finalize the full edge vocabulary of KLRE.

At the roadmap level, KLRE should define the category of relationships
each graph layer is responsible for.

Concrete edge names, schemas, constraints, and extraction rules belong to
later implementation design.

For example, this roadmap may say:

```text
Layer 1 needs hierarchy and sibling-order relationships.
```

It should not permanently lock the implementation into edge names such as:

```text
CONTAINS
NEXT
PART_OF
PREVIOUS
```

The same principle applies to higher layers. This roadmap does not
finalize names such as:

```text
REFERS_TO
DELEGATES_TO
DEFINES
USES_TERM
IMPOSES_DUTY_ON
PENALIZES
REQUIRES
VIOLATES
```

Those names belong to later design stages after retrieval, parsing, and
reasoning use cases are clearer.

## Layer 1: Structural Graph

Layer 1 represents the explicit structure of Korean statutes.

It covers legal units such as:

- legal document
- part
- chapter
- section
- subsection
- article
- paragraph
- subparagraph
- item
- supplementary provision
- annex
- form

Layer 1 should support structural relationship categories:

- hierarchy / containment
- sibling order / legal reading order

Layer 1 is deterministic and rule-based.

Its purpose is to support:

- stable legal node identity
- citation anchoring
- hierarchy traversal
- sibling traversal
- legal reading order
- statute visualization
- deterministic retrieval support
- future reference anchoring
- future definition anchoring
- future semantic annotation

Each legal document is the root of its own Layer 1 structural graph.

For example, an Act, Enforcement Decree, and Enforcement Rule each have
their own Layer 1 structural graph:

```text
Act -> articles
Enforcement Decree -> articles
Enforcement Rule -> articles
```

Layer 1 must not represent this as structural containment:

```text
Act -> Enforcement Decree
```

Graph work in Phase 1 should focus on this layer only.

## Layer 2: Reference Graph

Layer 2 represents explicit references between legal text units.

Examples:

```text
제4조에 따른
대통령령으로 정하는
별표 1에 따른
「산업안전보건법」 제2조
```

Layer 2 should eventually model relationships where one legal unit
explicitly points to another legal unit, statute, annex, delegated rule, or
external legal source.

Layer 2 should be built only after Layer 1 has stable node identity and
citation anchoring.

Layer 2 is partially automatable through reference parsing and reference
resolution rules.

Layer 2 must support dangling references. When an explicit reference points
outside the retained corpus or cannot be resolved to a stable Layer 1
anchor, the reference should remain as a typed unresolved / out-of-corpus
reference record rather than being dropped or forced onto an incorrect
target.

The requirement is that unresolved references be typed. This roadmap does
not finalize the concrete unresolved-reference type vocabulary or reference
edge vocabulary.

## Layer 3: Definition Graph

Layer 3 represents explicitly defined legal terms.

It should connect:

- provisions that define terms
- scoped legal term concepts
- provisions that use those terms

Conceptually:

```text
[중대재해처벌법 제2조 제9호]
  defines
[경영책임자등]

[중대재해처벌법 제4조 제1항]
  uses
[경영책임자등]
```

Layer 3 is partially automatable because Korean statutes often contain
recognizable definition patterns:

```text
“X”란 ...
이 법에서 사용하는 용어의 뜻은 다음과 같다.
```

Definition modeling must be scoped.

A legal term should not be treated as a global string-only node. This is
too weak:

```text
[TERM: 사업주]
```

A term's meaning depends on:

- defining law
- defining provision
- effective version
- legal scope
- cross-law reference context

Therefore, Layer 3 must rely on stable Layer 1 anchors.

This roadmap does not finalize the concrete definition edge vocabulary.

## Layer 4: Legal Semantic Graph

Layer 4 represents higher-level legal meaning.

It may eventually model concepts such as:

- obligation
- prohibition
- permission
- exception
- penalty
- legal requirement
- legal effect
- actor
- compliance duty
- condition
- violation

Layer 4 must not be rushed.

Layer 4 requires legal interpretation, not just structural parsing.
It belongs to a semi-automated and human-reviewed modeling layer.

Layer 4 is qualitatively different from Layers 1-3. It is closer to legal
ontology / NLI research than deterministic parsing or reference extraction.
Any Layer 4 implementation commitment should require either significant
scope reduction to a narrow, testable semantic slice or external
collaboration with legal-domain / ontology expertise.

This roadmap does not finalize the ontology or relationship vocabulary for
Layer 4.

## Phase-1 graph scope

Phase-1 graph work should focus only on Layer 1.

The goal of Phase-1 graph work is:

```text
Define a deterministic structural graph projection contract over current
Korean statute ERD rows.
```

This does not replace ADR-019's Phase-1 hybrid retrieval baseline. It
defines the graph-modeling boundary inside Phase 1.

The Phase-1 structural graph projection is bounded by ADR-019's SAPA + OSH
corpus. Expansion requires the corpus boundary to widen first.

Layer 1 projection visibility follows ADR-013 temporal semantics. Effective-
as-of projection uses `effective_at <= requested_at` and
`superseded_at IS NULL OR requested_at < superseded_at`; `is_head` is
ingestion-lineage metadata, not the legal-effectiveness gate.

Phase-1 graph work should prioritize:

- stable node identity
- stable citation anchoring
- stable hierarchy
- stable ordering
- stable source traceability
- version-aware design
- retrieval-ready traversal

Phase-1 graph work should define the structural identity and traversal
foundation that later layers can safely depend on.

## Phase-1 graph decisions

### 1. Keep the current ERD

The current ERD remains the Phase-1 source of truth.

It should not be replaced by a graph database or graph-first model.

The graph should be projected from the existing normalized legal storage.

### 2. Add a graph projection layer

KLRE should introduce a graph projection layer derived from the ERD.

The graph projection should provide a uniform way to identify, traverse,
cite, and visualize legal units such as:

- legal documents
- structural text units
- supplementary provisions
- annexes
- forms

The graph projection should not own canonical legal data.

In Phase 1, the graph projection is a contract, not new storage:

- stable graph-node identities derived from existing source rows
- traversal semantics over existing parent/ordering fields
- citation anchors and hierarchy context derived from existing source
  tables

It should be reproducible from the ERD. If the ERD is rebuilt from the same
source data, the Layer 1 graph projection contract should produce the same
node identities and structural relationships.

Manual graph edits are not allowed in Phase 1.

Physical graph infrastructure is deferred. This includes graph tables,
materialized graph views, external graph stores, projection jobs, and graph
refresh scheduling.

### 3. Keep Phase-1 relationships structural

Phase 1 should only model structural relationship categories:

- hierarchy / containment
- sibling order / legal reading order

Phase 1 should not model semantic, interpretive, or legal reasoning
relationships.

Detailed edge names belong to a separate implementation document.

### 4. Preserve stable Layer 1 node identity

Layer 1 node identity must be stable across ingestion runs for the same
canonical source slice:

```text
(law_id, mst, effective_date)
```

This is same-version stability, not cross-amendment continuity.

Graph node identity should not depend only on database surrogate IDs.

It should be derived from stable legal identifiers such as:

- document identity
- version identity
- legal unit type
- legal unit number
- structural path

ADR-012's `node_key` is part of the Layer 1 same-version identity
contract. It is not a cross-amendment persistent identifier. 호-level shifts
and other structural amendments may invalidate keys across versions.

Each Layer 1 source kind must have a deterministic,
content-position-derived identity rule under its owning document:

- `structure_nodes` use ADR-012's `node_key`.
- `annexes` use their stable annex source-row identifiers, such as annex
  number / key and title, under the owning document.
- `supplementary_provisions` use their stable supplementary-provision
  source-row identifiers, such as supplementary-provision number / key and
  source order, under the owning document.
- `forms` use their stable form source-row identifiers, such as form number
  / key and title, under the owning document.

The exact graph node identity string format is an implementation detail.
The inputs that determine the identity are roadmap-fixed.

Layer 1 node identity is structural and version-scoped; it is not derived
from content hash. `source_content_hash` per ADR-021 tracks row content
within a node for result envelopes, caches, and eval rows, not the node's
identity.

Therefore, Layer 1 identity supports stable citation anchors, caches,
embeddings, and eval rows within a retained source slice. Cross-amendment
continuity, amendment diffing, and "same provision across versions"
resolution require a later identity/linkage model and are not guaranteed by
this roadmap.

Stable node identity is required for:

- citation anchoring
- deterministic retrieval
- graph traversal
- graph visualization
- future reference resolution
- future definition anchoring
- future semantic annotation
- retrieval cache stability within a source slice
- embedding/index stability within a source slice

### 5. Treat each legal document as its own structural root

Each legal document should be treated as the root of its own Layer 1
structural graph.

The Act and the Enforcement Decree are separate legal documents. They may
be related later, but they are not structurally contained within each
other.

At roadmap level, a Phase-1 Layer 1 document package has this shape under
one legal document root:

```text
legal document
  structural text hierarchy
    part / chapter / section / subsection / article / paragraph /
    subparagraph / item
  supplementary provisions
  annexes
  forms
```

This is a package-shape statement, not edge vocabulary, table design, or a
physical graph schema. The structural text hierarchy carries hierarchy and
legal reading order. Supplementary provisions, annexes, and forms are
document-package units under the owning legal document; they are not
children of articles in Phase 1. Annex and form attachments remain
resources or provenance records, not primary Layer 1 graph nodes.

Phase 1 should not define one merged document-wide reading-order chain
across all package units. Ordering is package-local:

- structural text hierarchy has its own legal reading-order chain;
- supplementary provisions have their own source-order chain;
- annexes have their own annex-order chain;
- forms have their own form-order chain.

### 6. Treat article branches as ordering, not relationships

Article branches such as:

```text
제4조의2
제4조의3
```

are independent article units inserted into the statutory order.

They should be handled through numbering and ordering, not through special
relationship categories such as:

```text
branch of
has branch
derived from article
```

Article branching belongs to structural numbering and ordering. It does
not require a separate graph relationship category.

### 7. Treat deleted provisions as status or exclusion, not relationships

Deleted provisions are not graph relationships.

A deleted provision should either be:

- excluded from the active structural graph, or
- represented as a legal unit with deleted status if source-faithful
  visualization is required later

Deletion is not an edge category. It is a lifecycle/status issue or an
active-graph projection policy.

### 8. Do not treat Act -> Enforcement Decree as Layer 1 containment

The ERD may store document-level relationships such as:

```text
법률 -> 시행령
법률 -> 시행규칙
```

However, this is not structural containment.

An Enforcement Decree is not contained inside an Act.

Act-to-decree relationships belong to a later document-level or
reference-level graph, not the Phase-1 structural graph.

ADR-009 is the locus for the current ERD shape and population rule for
`legal_documents.parent_doc_id`. Any future work on Act-to-Decree or
Act-to-Rule document linkage, including the known 시행규칙 parentage revisit,
should be handled by ADR-009 or an explicit ADR-009 follow-up. This roadmap
section only states that such document linkage is not Layer 1 structural
containment.

### 9. Keep supplementary provisions simple in Phase 1

Supplementary provisions should be included as legal text units in the
structural graph.

Phase 1 does not need to fully parse their internal article-level
structure.

In Phase 1, supplementary provisions should be represented as coarse legal
text units attached to the relevant legal document.

Their internal article-level structure, effective-date logic,
transitional measures, and applicability rules are deferred.

### 10. Keep annexes as legal content units

Annexes should be included in the structural graph.

Annex content is legally meaningful and should remain available for
retrieval.

Per ADR-001, annexes are document-level legal content units, not children
inside the article hierarchy and not article siblings in the article legal
reading order. They participate in Layer 1 as separately addressable units
under the document package, with their own annex ordering, not as part of
the article sibling-order chain.

`annex_attachments` should be treated as resources or provenance records,
not primary graph nodes in Phase 1.

### 11. Keep forms as legal package units

Forms should be represented in the structural graph because they are part
of the statute package.

Phase 1 does not need full semantic parsing of form contents.

Forms are statute package units whose metadata should be represented
structurally, but whose internal semantic content does not need to become a
Phase-1 retrieval target unless explicitly required later.

`form_attachments` should be treated as resources or provenance records,
not primary graph nodes in Phase 1.

## Phase-1 graph invariants

The following invariants are a compact restatement of the Phase-1 graph
decisions for downstream reference. They introduce no separate commitments.
If this list appears to drift from the numbered decisions above or the layer
roadmap sections, the numbered decisions and layer sections control.

1. The ERD remains the canonical source of truth.
2. The graph is derived from the ERD.
3. Layer 1 graph projection is deterministic and reproducible.
4. Layer 1 models structure only.
5. Each legal document is the root of its own structural graph.
6. Act-to-decree relationships are not structural containment.
7. Article branches are ordering issues, not graph relationship types.
8. Deleted provisions are lifecycle/status issues, not graph relationship
   types.
9. Supplementary provisions are coarse legal text units in Phase 1.
10. Annexes are legal content units.
11. Forms are legal package units.
12. Higher-level legal meaning is deferred to later layers.

## Phase-1 graph non-goals

Phase-1 graph work should not attempt to solve:

- legal interpretation
- obligation extraction
- penalty condition modeling
- legal issue graph construction
- full NLI
- legal reasoning
- chatbot answer generation
- semantic ontology design
- reference resolution
- definition scope resolution
- legal norm modeling
- complete temporal reasoning
- document-level delegation graph
- full parsing of supplementary provisions
- full semantic parsing of form attachments
- final edge vocabulary design for Layers 2-4
- manual graph curation
- graph-first replacement of normalized storage

## Options considered

| Option | Verdict |
|--------|---------|
| A. Replace the normalized ERD with graph-first storage | rejected — loses the canonical source model and creates premature graph ownership |
| B. Maintain graph as an independent source of truth | rejected — risks divergence from source ERDs |
| C. Jump directly to legal semantic graph modeling | rejected — legal meaning requires stable anchors and reviewed interpretation |
| D. Defer all graph thinking until after retrieval | rejected — deterministic retrieval and future reference/definition modeling need stable anchors now |
| E. Define a derived graph projection contract over the ERD, starting with Layer 1 structure | recommended — preserves normalized storage while preparing retrieval and future legal intelligence |

## Consequences

- The ERD remains canonical storage.
- The graph becomes a deterministic derived projection contract in Phase 1.
- Phase-1 graph work is limited to the structural graph projection
  contract.
- Phase 1 does not introduce physical graph storage unless a later ADR
  explicitly accepts it.
- Higher graph layers are explicitly future work:
  - Layer 2: explicit references
  - Layer 3: scoped definitions
- Layer 4: legal semantic graph, requiring explicit scope reduction or
  external legal-domain / ontology collaboration before implementation
- Graph implementation details need separate ADRs before schema, migration,
  projection, or extraction work.
- The first graph implementation must favor stable node identity and
  citation anchoring over semantic ambition.

## Graph-roadmap stage summary

These graph stages are not the same as project phases such as ADR-019's
Phase-1 SAPA + OSH retrieval baseline. They are graph-modeling stages that
may be implemented across project phases as the retrieval system matures.

Graph stages 1-4 implement Layers 1-4 respectively.

```text
Graph Stage 1:
Structural graph projection contract over the current ERD

Graph Stage 2:
Explicit reference graph based on stable Layer 1 anchors

Graph Stage 3:
Definition graph based on scoped legal terms and stable statutory anchors

Graph Stage 4:
Legal semantic graph with semi-automated and human-reviewed modeling
```

## Acceptance criteria

- The current ERD remains the source of truth.
- The graph is documented as a derived projection contract, not canonical
  storage.
- Phase-1 graph scope is limited to deterministic Layer 1 structural graph
  projection over existing ERD rows.
- Phase-1 Layer 1 visibility follows ADR-013 effective-as-of semantics:
  `effective_at <= requested_at` and
  `superseded_at IS NULL OR requested_at < superseded_at`; `is_head` is not
  the legal-effectiveness gate.
- Phase 1 does not require new graph tables, views, materialized views,
  external graph stores, or projection jobs.
- Given the same retained source XML and ERD rebuild, Layer 1 projection
  produces identical graph node identities and structural relationship
  categories.
- Each Layer 1 source kind has a deterministic identity rule fixed by
  source-kind inputs: `structure_nodes.node_key`, annex source-row
  identifiers, supplementary-provision source-row identifiers, and form
  source-row identifiers under the owning document.
- Layer 1 supports hierarchy / containment and sibling-order / legal
  reading-order relationship categories.
- Each legal document is treated as its own structural root.
- The Phase-1 document package shape under each legal document root
  distinguishes the structural text hierarchy from supplementary
  provisions, annexes, and forms.
- Phase 1 uses package-local ordering chains for structural text,
  supplementary provisions, annexes, and forms; it does not define one
  merged document-wide reading-order chain.
- Act-to-decree relationships are excluded from Layer 1 structural
  containment.
- Supplementary provisions, annexes, and forms are included at the
  roadmap level with Phase-1 simplifications.
- Future Layer 2 design preserves unresolved / out-of-corpus references as
  typed records; the concrete unresolved-reference type vocabulary and
  reference edge vocabulary remain deferred.
- Any Layer 4 implementation commitment requires significant scope
  reduction to a narrow, testable semantic slice or external legal-domain /
  ontology collaboration.
- Detailed edge vocabulary, graph schema, projection jobs, and extraction
  rules remain deferred to implementation ADRs.
