from datetime import date
from pathlib import Path

import pytest

from ingest.parse import parse_annex_attachments, parse_annexes, parse_doc, sha256_text
from ingest.records import Document


def test_parse_phase_1_act_has_no_annexes() -> None:
    doc = parse_doc(Path("data/raw/eflaw/013993/228817/20220127.xml"))

    assert parse_annexes(doc) == []
    assert parse_annex_attachments(doc) == []


def test_parse_phase_1_decree_annexes() -> None:
    doc = parse_doc(Path("data/raw/eflaw/014159/277417/20251001.xml"))
    annexes = parse_annexes(doc)

    assert [annex.annex_key for annex in annexes] == [
        "000100E",
        "000200E",
        "000300E",
        "000400E",
        "000500E",
    ]
    assert [annex.number for annex in annexes] == ["1", "2", "3", "4", "5"]
    assert [annex.branch_number for annex in annexes] == [None] * 5
    assert [annex.content_format for annex in annexes] == [None] * 5
    assert [annex.source_url for annex in annexes] == [None] * 5

    first = annexes[0]
    assert first.title == "직업성 질병(제2조 관련)"
    assert first.content_text.startswith(
        "■ 중대재해 처벌 등에 관한 법률 시행령 [별표 1]"
    )
    assert first.content_hash == sha256_text(first.content_text)


def test_parse_phase_1_decree_annex_content_delayouts_hard_wraps() -> None:
    doc = parse_doc(Path("data/raw/eflaw/014159/277417/20251001.xml"))
    annexes = {annex.annex_key: annex for annex in parse_annexes(doc)}

    first = annexes["000100E"].content_text
    assert "노출되어 발생한 중추신경계장해" in first
    assert "유기화합물에 노출되어" in first
    assert "발생한 렙토스피라증" in first
    assert "심부체온상승을 동반하는 열사병" in first

    third = annexes["000300E"].content_text
    assert "교량 중심선에 따라 측정한 거리를 말한다" in third
    assert "각 본체 구간과 하나의 구조로 연결된 구간을 포함한 거리를 말한다" in third
    assert "측정한 거\n리를 말한다" not in third


def test_parse_phase_1_decree_annex_attachments() -> None:
    doc = parse_doc(Path("data/raw/eflaw/014159/277417/20251001.xml"))
    attachments = parse_annex_attachments(doc)

    assert len(attachments) == 21
    assert [a.attachment_type for a in attachments].count("hwp") == 5
    assert [a.attachment_type for a in attachments].count("pdf") == 5
    assert [a.attachment_type for a in attachments].count("image") == 11

    first_hwp = attachments[0]
    assert first_hwp.annex_key == "000100E"
    assert first_hwp.attachment_type == "hwp"
    assert first_hwp.source_attachment_url == "/LSW/flDownload.do?flSeq=157760599"
    assert first_hwp.source_filename == "law0141592025100135805KC_000100E_20251001.hwp"
    assert first_hwp.stored_file_path is None
    assert first_hwp.checksum_sha256 is None
    assert first_hwp.fetched_at is None

    first_images = [
        a.source_filename
        for a in attachments
        if a.annex_key == "000100E" and a.attachment_type == "image"
    ]
    assert first_images == [
        "000100110201_P1_20251001.gif",
        "000100110201_P2_20251001.gif",
    ]
    assert all(
        a.source_attachment_url is None
        for a in attachments
        if a.attachment_type == "image"
    )


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"key": "00100E"}, "invalid 별표키 shape"),
        ({"key": "000100E", "kind": "서식"}, "requires F-suffixed"),
        ({"kind": "기타"}, "unsupported 별표구분"),
        ({"key": "000200E", "number": "0001"}, "disagrees with XML fields"),
        ({"key": "000102E", "branch": "00"}, "disagrees with XML fields"),
        ({"title": " "}, "required <별표제목> missing or empty"),
        ({"content": " "}, "required <별표내용> empty after normalization"),
    ],
)
def test_annex_parser_halts_on_adr_014_violations(
    tmp_path: Path, override: dict[str, str], message: str
) -> None:
    doc = _annex_doc(tmp_path, override)

    with pytest.raises(ValueError, match=message):
        parse_annexes(doc)


def _annex_doc(tmp_path: Path, override: dict[str, str]) -> Document:
    values = {
        "key": "000100E",
        "number": "0001",
        "branch": "00",
        "kind": "별표",
        "title": "테스트 별표",
        "content": "본문",
    } | override
    xml_path = tmp_path / "sample.xml"
    xml_path.write_text(
        f"""<법령>
<별표>
<별표단위 별표키="{values['key']}">
<별표번호>{values['number']}</별표번호>
<별표가지번호>{values['branch']}</별표가지번호>
<별표구분>{values['kind']}</별표구분>
<별표제목>{values['title']}</별표제목>
<별표내용>{values['content']}</별표내용>
</별표단위>
</별표>
</법령>
""",
        encoding="utf-8",
    )
    return Document(
        law_id="sample",
        mst=1,
        xml_path=xml_path,
        title="sample",
        title_abbrev=None,
        law_number="1",
        doc_type="대통령령",
        doc_type_code=None,
        amendment_type="제정",
        enacted_date=date(2026, 1, 1),
        effective_date=date(2026, 1, 1),
        competent_authority="sample",
        competent_authority_code="1",
        structure_code=None,
        legislation_reason=None,
        source_url="sample",
        content_hash="sample",
    )
