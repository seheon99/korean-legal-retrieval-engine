from pathlib import Path

from ingest.parse import (
    parse_doc,
    parse_form_attachments,
    parse_forms,
    parse_supplementary_provisions,
)


def test_parse_sapa_act_supplementary_provisions() -> None:
    doc = parse_doc(Path("data/raw/eflaw/013993/228817/20220127.xml"))
    provisions = parse_supplementary_provisions(doc)

    assert len(provisions) == 1
    provision = provisions[0]
    assert provision.provision_key == "2021012617907"
    assert provision.promulgated_date.isoformat() == "2021-01-26"
    assert provision.promulgation_number == 17907
    assert "50명 미만인 사업 또는 사업장" in provision.content


def test_parse_osh_rule_forms_and_attachments() -> None:
    doc = parse_doc(Path("data/raw/eflaw/007364/271485/20260101.xml"))
    forms = parse_forms(doc)
    attachments = parse_form_attachments(doc)

    assert len(forms) == 111
    assert len(attachments) == 356

    first = forms[0]
    assert first.form_key == "000100F"
    assert first.number == "1"
    assert first.branch_number is None
    assert first.title == "통합 산업재해 현황 조사표"
    assert first.source_url is None

    first_attachments = [a for a in attachments if a.form_key == "000100F"]
    assert [a.attachment_type for a in first_attachments] == [
        "hwp",
        "pdf",
        "image",
        "image",
    ]
    assert (
        first_attachments[0].source_attachment_url
        == "/LSW/flDownload.do?flSeq=159570571"
    )
    assert (
        first_attachments[0].source_filename
        == "law0073642025053000443KC_000100F_20260101.hwp"
    )
    assert first_attachments[2].source_filename == "000100110202_P1_20260101.gif"
