"""Korean legal corpus ingestion pipeline (load layer).

Loads raw 법제처 OpenAPI XML from `data/raw/{law_id}/{mst}.xml`
(per ADR-011) into the Phase-1 statute schema (per ADR-010).

Implements the ADR-009 population rule:
  Acts → Decrees → Rules. Decree.parent_doc_id is resolved by
  stripping ' 시행령' from the title and looking up the current Act
  via `ux_legal_documents_current_act_title`. Rules.parent_doc_id is
  left NULL (ADR-009 patch #5: 부령 제1조 delegation parsing
  deferred until first 시행규칙-bearing statute enters scope).

The retrieval engine is a separate sibling package under `src/`.
"""
