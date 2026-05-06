"""Korean legal corpus ingestion pipeline (load layer).

Loads canonical 법제처 `eflaw` XML from
`data/raw/eflaw/{law_id}/{mst}/{efYd}.xml` (per ADR-020) into the
Phase-1 statute schema (per ADR-010).

Implements the ADR-009 population rule:
  Acts → Decrees → Rules. Decree.parent_doc_id is resolved by
  stripping ' 시행령' from the title and looking up the head Act
  via `ux_legal_documents_head_act_title`. Rules.parent_doc_id is
  left NULL (ADR-009 patch #5: 부령 제1조 delegation parsing
  remains deferred).

The retrieval engine is a separate sibling package under `src/`.
"""
