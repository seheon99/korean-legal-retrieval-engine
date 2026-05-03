"""Parse raw 법제처 OpenAPI XML into in-memory `Document` records.

Doc-level fields only — children (조문/부칙/별표/별지서식) are the
deferred parser depth per the Mermaid skeleton. Sufficient to drive
the ADR-009 population rule end-to-end.
"""

from __future__ import annotations

import hashlib
import xml.etree.ElementTree as ET
from datetime import date, datetime
from pathlib import Path

from .records import Document


_VALID_DOC_TYPES = ("법률", "대통령령", "총리령", "부령")


def discover(raw_dir: Path) -> list[Path]:
    """Return XML paths under `data/raw/{law_id}/{mst}.xml` (ADR-011)."""
    return sorted(raw_dir.glob("*/*.xml"))


def parse_doc(xml_path: Path) -> Document:
    """Extract doc-level fields from one raw XML file."""
    mst = int(xml_path.stem)
    law_id = xml_path.parent.name

    info = ET.parse(xml_path).getroot().find("기본정보")
    if info is None:
        raise ValueError(f"{xml_path}: <기본정보> not found")

    def text(tag: str) -> str | None:
        el = info.find(tag)
        return el.text.strip() if el is not None and el.text is not None else None

    def required(tag: str) -> str:
        v = text(tag)
        if v is None:
            raise ValueError(f"{xml_path}: required <{tag}> missing or empty")
        return v

    def yyyymmdd(tag: str) -> date:
        return datetime.strptime(required(tag), "%Y%m%d").date()

    doc_type_el = info.find("법종구분")
    if doc_type_el is None or doc_type_el.text is None:
        raise ValueError(f"{xml_path}: <법종구분> missing")
    doc_type_text = doc_type_el.text.strip()
    if doc_type_text not in _VALID_DOC_TYPES:
        # ADR-006 verification trigger candidate (e.g., 행정안전부령).
        # Per-ministry shape handling lives in a follow-up; fail fast.
        raise ValueError(
            f"{xml_path}: unsupported doc_type {doc_type_text!r}; "
            f"ADR-006 verification trigger required."
        )

    auth_el = info.find("소관부처")
    if auth_el is None or auth_el.text is None:
        raise ValueError(f"{xml_path}: <소관부처> missing")
    auth_code = auth_el.attrib.get("소관부처코드")
    if not auth_code:
        raise ValueError(f"{xml_path}: <소관부처> missing 소관부처코드 attribute")

    return Document(
        law_id=law_id,
        mst=mst,
        xml_path=xml_path,
        title=required("법령명_한글"),
        title_abbrev=text("법령명약칭"),
        law_number=required("공포번호"),
        doc_type=doc_type_text,  # type: ignore[arg-type]
        doc_type_code=doc_type_el.attrib.get("법종구분코드"),
        amendment_type=required("제개정구분"),
        enacted_date=yyyymmdd("공포일자"),
        effective_date=yyyymmdd("시행일자"),
        competent_authority=auth_el.text.strip(),
        competent_authority_code=auth_code,
        structure_code=text("편장절관"),
        legislation_reason=None,
        source_url=(
            f"https://www.law.go.kr/DRF/lawService.do"
            f"?target=law&MST={mst}&type=XML"
        ),
        content_hash=sha256_file(xml_path),
    )


def sha256_file(path: Path) -> str:
    """SHA-256 hex of the file — the ADR-011 integrity link to
    `legal_documents.content_hash`."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()
