"""In-memory record types for the ingestion pipeline.

`Document` carries one row's worth of `legal_documents` data plus the
source XML path. `parent_doc_id` is intentionally absent — it is
resolved by populate.py per the ADR-009 population rule, not by the
parser.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict


DocType = Literal["법률", "대통령령", "총리령", "부령"]


class Document(BaseModel):
    model_config = ConfigDict(frozen=True)

    law_id: str
    mst: int
    xml_path: Path

    title: str
    title_abbrev: str | None
    law_number: str
    doc_type: DocType
    doc_type_code: str | None
    amendment_type: str
    enacted_date: date
    effective_date: date
    competent_authority: str
    competent_authority_code: str
    structure_code: str | None
    legislation_reason: str | None

    source_url: str
    content_hash: str
