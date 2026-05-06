from pathlib import Path

import pytest

from ingest.parse import discover, parse_doc


def test_discover_uses_canonical_eflaw_paths(tmp_path: Path) -> None:
    raw_dir = tmp_path / "data" / "raw"
    legacy = raw_dir / "001766" / "283449.xml"
    canonical = raw_dir / "eflaw" / "001766" / "283449" / "20260601.xml"
    legacy.parent.mkdir(parents=True)
    canonical.parent.mkdir(parents=True)
    legacy.write_text("<법령 />", encoding="utf-8")
    canonical.write_text("<법령 />", encoding="utf-8")

    assert discover(raw_dir) == [canonical]


def test_parse_doc_preserves_eflaw_source_identity(tmp_path: Path) -> None:
    xml_path = _write_doc(
        tmp_path / "data" / "raw" / "eflaw" / "001766" / "283449" / "20260601.xml",
        effective_date="20260601",
    )

    doc = parse_doc(xml_path)

    assert doc.law_id == "001766"
    assert doc.mst == 283449
    assert doc.effective_date.isoformat() == "2026-06-01"
    assert doc.source_url == (
        "https://www.law.go.kr/DRF/lawService.do"
        "?target=eflaw&MST=283449&efYd=20260601&type=XML"
    )


def test_parse_doc_rejects_eflaw_path_date_mismatch(tmp_path: Path) -> None:
    xml_path = _write_doc(
        tmp_path / "data" / "raw" / "eflaw" / "001766" / "283449" / "20260601.xml",
        effective_date="20260801",
    )

    with pytest.raises(ValueError, match="path efYd"):
        parse_doc(xml_path)


def test_parse_doc_normalizes_ministry_prefixed_rule_type(tmp_path: Path) -> None:
    xml_path = _write_doc(
        tmp_path / "data" / "raw" / "eflaw" / "007364" / "271485" / "20260101.xml",
        effective_date="20260101",
        doc_type="고용노동부령",
        doc_type_code="A0097",
    )

    doc = parse_doc(xml_path)

    assert doc.law_id == "007364"
    assert doc.mst == 271485
    assert doc.doc_type == "부령"
    assert doc.doc_type_code == "A0097"


def _write_doc(
    xml_path: Path,
    *,
    effective_date: str,
    doc_type: str = "법률",
    doc_type_code: str = "A0002",
) -> Path:
    xml_path.parent.mkdir(parents=True)
    xml_path.write_text(
        f"""<?xml version="1.0" encoding="UTF-8"?>
<법령>
  <기본정보>
    <법령ID>001766</법령ID>
    <법령명_한글>산업안전보건법</법령명_한글>
    <법령명약칭>산안법</법령명약칭>
    <공포번호>00000</공포번호>
    <법종구분 법종구분코드="{doc_type_code}">{doc_type}</법종구분>
    <제개정구분>일부개정</제개정구분>
    <공포일자>20260219</공포일자>
    <시행일자>{effective_date}</시행일자>
    <소관부처 소관부처코드="1492000">고용노동부</소관부처>
    <편장절관>11000000</편장절관>
  </기본정보>
</법령>
""",
        encoding="utf-8",
    )
    return xml_path
