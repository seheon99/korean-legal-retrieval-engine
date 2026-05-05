"""Parse raw 법제처 OpenAPI XML into in-memory records."""

from __future__ import annotations

import hashlib
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from .records import Annex, AnnexAttachment, Document, StructureNode


_VALID_DOC_TYPES = ("법률", "대통령령", "총리령", "부령")
_ARTICLE_KEY_RE = re.compile(r"^[0-9]{7}$")
# `<별표단위 별표키>` is shared: E = annex row, F = form row.
_ANNEX_FORM_KEY_RE = re.compile(r"^[0-9]{6}[EF]$")
_LEADING_INT_RE = re.compile(r"^(\d+)")
_DISALLOWED_BRANCH_TAGS = ("편", "장", "절", "관", "항", "목")


@dataclass(frozen=True)
class _ParsedAnnexUnit:
    element: ET.Element
    unit_key: str
    kind: str
    number: str
    branch_number: str | None
    title: str
    content_text: str | None


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


def parse_structure_nodes(doc: Document) -> list[StructureNode]:
    """Parse the statute body into `structure_nodes` rows.

    Scope is intentionally the 조문 block only. 부칙/별표/서식 stay out of
    this parser pass.
    """
    root = ET.parse(doc.xml_path).getroot()
    _assert_no_disallowed_branch_elements(root, doc.xml_path)

    body = root.find("조문")
    if body is None:
        return []

    nodes: list[StructureNode] = []
    stack: dict[int, str] = {}
    seen_keys: set[str] = set()

    for unit in body.findall("조문단위"):
        article_key = unit.attrib.get("조문키")
        if not article_key:
            raise ValueError(f"{doc.xml_path}: <조문단위> missing 조문키")
        _assert_article_key_matches_xml(unit, article_key, doc.xml_path)

        article_kind = _required_text(unit, "조문여부", doc.xml_path)
        level = 2 if article_kind == "전문" else 5
        parent_node_key = _nearest_parent_key(stack, level)
        node = StructureNode(
            parent_node_key=parent_node_key,
            level=level,
            node_key=article_key,
            number=_normalize_article_number(unit, doc.xml_path),
            title=_text(unit, "조문제목"),
            content=_required_text(unit, "조문내용", doc.xml_path),
            sort_key=article_key,
            effective_date=_date_text(unit, "조문시행일자", doc.xml_path),
            is_changed=_changed_flag(_text(unit, "조문변경여부"), doc.xml_path),
            source_url=None,
            content_hash=sha256_text(_required_text(unit, "조문내용", doc.xml_path)),
        )
        _append_node(nodes, seen_keys, node, doc.xml_path)
        _push_stack(stack, level, article_key)

        if level != 5:
            continue

        effective_date = node.effective_date
        is_changed = node.is_changed
        explicit_para_index = 0
        implicit_para_seen = False

        for para in unit.findall("항"):
            para_number = _text(para, "항번호")
            if para_number is None:
                if implicit_para_seen:
                    raise ValueError(
                        f"{doc.xml_path}: multiple implicit <항> under "
                        f"조문키={article_key}"
                    )
                implicit_para_seen = True
                para_segment = "00"
                para_number = ""
                para_content = ""
            else:
                explicit_para_index += 1
                para_segment = f"{explicit_para_index:02d}"
                para_content = _required_text(para, "항내용", doc.xml_path)

            para_key, para_sort = _compose_para_key(article_key, para_segment)
            para_node = StructureNode(
                parent_node_key=article_key,
                level=6,
                node_key=para_key,
                number=para_number,
                title=None,
                content=para_content,
                sort_key=para_sort,
                effective_date=effective_date,
                is_changed=is_changed,
                source_url=None,
                content_hash=sha256_text(para_content),
            )
            _append_node(nodes, seen_keys, para_node, doc.xml_path)

            for item in para.findall("호"):
                item_number = _required_text(item, "호번호", doc.xml_path)
                item_branch_number = _text(item, "호가지번호")
                item_segment = _compose_item_segment(
                    item_number, item_branch_number, doc.xml_path
                )
                item_key, item_sort = _compose_item_key(para_key, para_sort, item_segment)
                item_content = _required_text(item, "호내용", doc.xml_path)
                item_node = StructureNode(
                    parent_node_key=para_key,
                    level=7,
                    node_key=item_key,
                    number=_normalize_item_number(
                        item_number, item_branch_number, doc.xml_path
                    ),
                    title=None,
                    content=item_content,
                    sort_key=item_sort,
                    effective_date=effective_date,
                    is_changed=is_changed,
                    source_url=None,
                    content_hash=sha256_text(item_content),
                )
                _append_node(nodes, seen_keys, item_node, doc.xml_path)

                for index, subitem in enumerate(item.findall("목"), start=1):
                    subitem_key, subitem_sort = _compose_subitem_key(
                        item_key, item_sort, index
                    )
                    subitem_content = _required_text(subitem, "목내용", doc.xml_path)
                    subitem_node = StructureNode(
                        parent_node_key=item_key,
                        level=8,
                        node_key=subitem_key,
                        number=_strip_trailing_dot(
                            _required_text(subitem, "목번호", doc.xml_path)
                        ),
                        title=None,
                        content=subitem_content,
                        sort_key=subitem_sort,
                        effective_date=effective_date,
                        is_changed=is_changed,
                        source_url=None,
                        content_hash=sha256_text(subitem_content),
                    )
                    _append_node(nodes, seen_keys, subitem_node, doc.xml_path)

    return nodes


def parse_annexes(doc: Document) -> list[Annex]:
    """Parse `<별표구분>별표</별표구분>` rows into `annexes` records."""
    annexes: list[Annex] = []
    seen_keys: set[str] = set()

    for unit in _parse_annex_units(doc):
        if unit.kind != "별표":
            continue

        annex_key = unit.unit_key
        if annex_key in seen_keys:
            raise ValueError(f"{doc.xml_path}: duplicate annex_key {annex_key!r}")
        seen_keys.add(annex_key)

        if unit.content_text is None:
            raise ValueError(f"{doc.xml_path}: annex content missing for {annex_key}")
        annexes.append(
            Annex(
                annex_key=annex_key,
                number=unit.number,
                branch_number=unit.branch_number,
                title=unit.title,
                content_text=unit.content_text,
                content_format=None,
                source_url=None,
                content_hash=sha256_text(unit.content_text),
            )
        )

    return annexes


def parse_annex_attachments(doc: Document) -> list[AnnexAttachment]:
    """Parse source attachment references for annex rows only.

    Form rows are validated by `_parse_annex_units()` but remain reserved
    for a later `forms` parser.
    """
    attachments: list[AnnexAttachment] = []

    for unit in _parse_annex_units(doc):
        if unit.kind != "별표":
            continue

        element = unit.element
        annex_key = unit.unit_key
        hwp_url = _text(element, "별표서식파일링크")
        hwp_filename = _text(element, "별표HWP파일명")
        if hwp_url is not None or hwp_filename is not None:
            attachments.append(
                AnnexAttachment(
                    annex_key=annex_key,
                    attachment_type="hwp",
                    source_attachment_url=hwp_url,
                    source_filename=hwp_filename,
                )
            )

        pdf_url = _text(element, "별표서식PDF파일링크")
        pdf_filename = _text(element, "별표PDF파일명")
        if pdf_url is not None or pdf_filename is not None:
            attachments.append(
                AnnexAttachment(
                    annex_key=annex_key,
                    attachment_type="pdf",
                    source_attachment_url=pdf_url,
                    source_filename=pdf_filename,
                )
            )

        for image_el in element.findall("별표이미지파일명"):
            filename = _element_text(image_el)
            if filename is None:
                raise ValueError(
                    f"{doc.xml_path}: empty <별표이미지파일명> for "
                    f"annex_key={annex_key}"
                )
            attachments.append(
                AnnexAttachment(
                    annex_key=annex_key,
                    attachment_type="image",
                    source_attachment_url=None,
                    source_filename=filename,
                )
            )

    return attachments


def sha256_file(path: Path) -> str:
    """SHA-256 hex of the file — the ADR-011 integrity link to
    `legal_documents.content_hash`."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _text(parent: ET.Element, tag: str) -> str | None:
    el = parent.find(tag)
    if el is None:
        return None
    return _element_text(el)


def _element_text(el: ET.Element) -> str | None:
    value = "".join(el.itertext()).strip()
    return value if value else None


def _required_text(parent: ET.Element, tag: str, xml_path: Path) -> str:
    value = _text(parent, tag)
    if value is None:
        raise ValueError(f"{xml_path}: required <{tag}> missing or empty")
    return value


def _normalized_element_text(el: ET.Element) -> str | None:
    value = "".join(el.itertext()).replace("\r\n", "\n").replace("\r", "\n").strip()
    return value if value else None


def _required_normalized_annex_content(unit: ET.Element, xml_path: Path) -> str:
    el = unit.find("별표내용")
    if el is None:
        raise ValueError(f"{xml_path}: required <별표내용> missing")
    value = _normalized_element_text(el)
    if value is None:
        raise ValueError(f"{xml_path}: required <별표내용> empty after normalization")
    return value


def _parse_annex_units(doc: Document) -> list[_ParsedAnnexUnit]:
    root = ET.parse(doc.xml_path).getroot()
    annex_root = root.find("별표")
    if annex_root is None:
        return []

    units: list[_ParsedAnnexUnit] = []
    seen_keys: set[str] = set()
    for unit in annex_root.findall("별표단위"):
        unit_key = unit.attrib.get("별표키")
        if not unit_key:
            raise ValueError(f"{doc.xml_path}: <별표단위> missing 별표키")
        if unit_key in seen_keys:
            raise ValueError(f"{doc.xml_path}: duplicate 별표키 {unit_key!r}")
        seen_keys.add(unit_key)

        kind = _required_text(unit, "별표구분", doc.xml_path)
        if kind not in ("별표", "서식"):
            raise ValueError(f"{doc.xml_path}: unsupported 별표구분 {kind!r}")
        _assert_annex_form_key_shape_and_kind(unit_key, kind, doc.xml_path)

        number, branch_number = _normalize_annex_form_number_fields(
            unit, unit_key, doc.xml_path
        )
        title = _required_text(unit, "별표제목", doc.xml_path)
        content_text = (
            _required_normalized_annex_content(unit, doc.xml_path)
            if kind == "별표"
            else None
        )
        units.append(
            _ParsedAnnexUnit(
                element=unit,
                unit_key=unit_key,
                kind=kind,
                number=number,
                branch_number=branch_number,
                title=title,
                content_text=content_text,
            )
        )

    return units


def _assert_annex_form_key_shape_and_kind(
    unit_key: str, kind: str, xml_path: Path
) -> None:
    if _ANNEX_FORM_KEY_RE.fullmatch(unit_key) is None:
        raise ValueError(f"{xml_path}: invalid 별표키 shape {unit_key!r}")
    if kind == "별표" and not unit_key.endswith("E"):
        raise ValueError(
            f"{xml_path}: 별표구분='별표' requires E-suffixed 별표키, got "
            f"{unit_key!r}"
        )
    if kind == "서식" and not unit_key.endswith("F"):
        raise ValueError(
            f"{xml_path}: 별표구분='서식' requires F-suffixed 별표키, got "
            f"{unit_key!r}"
        )


def _normalize_annex_form_number_fields(
    unit: ET.Element, unit_key: str, xml_path: Path
) -> tuple[str, str | None]:
    number = _parse_required_int(
        _required_text(unit, "별표번호", xml_path), "별표번호", xml_path
    )
    branch_number = _parse_optional_int(
        _text(unit, "별표가지번호"), "별표가지번호", xml_path
    )
    if number > 9999 or branch_number > 99:
        raise ValueError(
            f"{xml_path}: 별표번호/별표가지번호 exceeds key segment width "
            f"({number}, {branch_number})"
        )

    if unit_key[:4] != f"{number:04d}" or unit_key[4:6] != f"{branch_number:02d}":
        raise ValueError(
            f"{xml_path}: 별표키 {unit_key!r} disagrees with XML fields "
            f"(별표번호={number}, 별표가지번호={branch_number})"
        )

    return str(number), None if branch_number == 0 else str(branch_number)


def _date_text(parent: ET.Element, tag: str, xml_path: Path) -> date:
    return datetime.strptime(_required_text(parent, tag, xml_path), "%Y%m%d").date()


def _changed_flag(value: str | None, xml_path: Path) -> bool | None:
    if value is None:
        return None
    if value == "Y":
        return True
    if value == "N":
        return False
    raise ValueError(f"{xml_path}: invalid 조문변경여부 {value!r}")


def _normalize_article_number(unit: ET.Element, xml_path: Path) -> str:
    article_number = _required_text(unit, "조문번호", xml_path)
    branch_number = _text(unit, "조문가지번호")
    if branch_number is None:
        return article_number
    return f"{article_number}의{branch_number}"


def _normalize_item_number(
    item_number: str, branch_number: str | None, xml_path: Path
) -> str:
    base = _strip_trailing_dot(item_number)
    if branch_number is None:
        return base
    _parse_required_int(branch_number, "호가지번호", xml_path)
    return f"{base}의{branch_number}"


def _strip_trailing_dot(value: str) -> str:
    return value[:-1] if value.endswith(".") else value


def _assert_no_disallowed_branch_elements(root: ET.Element, xml_path: Path) -> None:
    for tag in _DISALLOWED_BRANCH_TAGS:
        branch_tag = f"{tag}가지번호"
        found = root.find(f".//{branch_tag}")
        if found is not None:
            raise ValueError(
                f"{xml_path}: unsupported <{branch_tag}> found; "
                "ADR-012 accepts branch numbering only at 조 and 호."
            )


def _assert_article_key_matches_xml(
    unit: ET.Element, article_key: str, xml_path: Path
) -> None:
    if _ARTICLE_KEY_RE.fullmatch(article_key) is None:
        raise ValueError(f"{xml_path}: invalid 조문키 shape {article_key!r}")

    article_number = _parse_required_int(
        _required_text(unit, "조문번호", xml_path), "조문번호", xml_path
    )
    branch_number = _parse_optional_int(
        _text(unit, "조문가지번호"), "조문가지번호", xml_path
    )
    article_kind = _required_text(unit, "조문여부", xml_path)
    if article_kind == "전문":
        kind_digit = 0
    elif article_kind == "조문":
        kind_digit = 1
    else:
        raise ValueError(f"{xml_path}: unsupported 조문여부 {article_kind!r}")

    decoded_article_number = int(article_key[:4])
    decoded_branch_number = int(article_key[4:6])
    decoded_kind_digit = int(article_key[6])
    if (
        decoded_article_number != article_number
        or decoded_branch_number != branch_number
        or decoded_kind_digit != kind_digit
    ):
        raise ValueError(
            f"{xml_path}: 조문키 {article_key!r} disagrees with XML fields "
            f"(조문번호={article_number}, 조문가지번호={branch_number}, "
            f"조문여부={article_kind})"
        )


def _parse_required_int(value: str, field: str, xml_path: Path) -> int:
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"{xml_path}: invalid <{field}> integer {value!r}") from exc


def _parse_optional_int(value: str | None, field: str, xml_path: Path) -> int:
    if value is None:
        return 0
    return _parse_required_int(value, field, xml_path)


def _nearest_parent_key(stack: dict[int, str], level: int) -> str | None:
    for parent_level in range(level - 1, 0, -1):
        parent_key = stack.get(parent_level)
        if parent_key is not None:
            return parent_key
    return None


def _push_stack(stack: dict[int, str], level: int, node_key: str) -> None:
    stack[level] = node_key
    for stale_level in [existing for existing in stack if existing > level]:
        del stack[stale_level]


def _append_node(
    nodes: list[StructureNode], seen_keys: set[str], node: StructureNode, xml_path: Path
) -> None:
    if node.node_key in seen_keys:
        raise ValueError(f"{xml_path}: duplicate structure node_key {node.node_key!r}")
    seen_keys.add(node.node_key)
    nodes.append(node)


def _compose_para_key(article_key: str, para_segment: str) -> tuple[str, str]:
    return f"{article_key}-{para_segment}", f"{article_key}.{para_segment}"


def _compose_item_segment(
    item_number: str, branch_number: str | None, xml_path: Path
) -> str:
    match = _LEADING_INT_RE.match(item_number.strip())
    if match is None:
        raise ValueError(f"{xml_path}: cannot parse <호번호> {item_number!r}")
    item_ordinal = int(match.group(1))
    branch_ordinal = _parse_optional_int(branch_number, "호가지번호", xml_path)
    if item_ordinal > 99 or branch_ordinal > 99:
        raise ValueError(
            f"{xml_path}: 호번호/호가지번호 exceeds ADR-012 two-digit segment "
            f"({item_ordinal}, {branch_ordinal})"
        )
    return f"{item_ordinal:02d}{branch_ordinal:02d}"


def _compose_item_key(
    para_key: str, para_sort: str, item_segment: str
) -> tuple[str, str]:
    return f"{para_key}-{item_segment}", f"{para_sort}.{item_segment}"


def _compose_subitem_key(
    item_key: str, item_sort: str, ordinal: int
) -> tuple[str, str]:
    if ordinal > 99:
        raise ValueError("목 ordinal exceeds ADR-012 two-digit segment")
    segment = f"{ordinal:02d}"
    return f"{item_key}-{segment}", f"{item_sort}.{segment}"
