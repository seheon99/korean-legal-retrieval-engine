from pathlib import Path

from ingest.parse import (
    _compose_item_key,
    _compose_item_segment,
    _compose_para_key,
    _compose_subitem_key,
    parse_doc,
    parse_structure_nodes,
)


def test_adr_012_key_composition() -> None:
    assert _compose_para_key("0002001", "00") == ("0002001-00", "0002001.00")
    assert _compose_para_key("0004001", "01") == ("0004001-01", "0004001.01")

    normal_item = _compose_item_segment("2.", None, Path("sample.xml"))
    assert normal_item == "0200"
    assert _compose_item_key("0004001-01", "0004001.01", normal_item) == (
        "0004001-01-0200",
        "0004001.01.0200",
    )

    branched_item = _compose_item_segment("7.", "2", Path("sample.xml"))
    assert branched_item == "0702"
    inline_branched_item = _compose_item_segment("3의2.", None, Path("sample.xml"))
    assert inline_branched_item == "0302"
    assert _compose_item_key("0001001-01", "0001001.01", branched_item) == (
        "0001001-01-0702",
        "0001001.01.0702",
    )

    assert _compose_subitem_key("0002001-00-0200", "0002001.00.0200", 1) == (
        "0002001-00-0200-01",
        "0002001.00.0200.01",
    )


def test_parse_phase_1_act_structure_nodes() -> None:
    nodes = _sample_nodes("data/raw/eflaw/013993/228817/20220127.xml")

    assert len(nodes) == 102
    assert nodes[0].level == 2
    assert nodes[0].node_key == "0001000"
    assert nodes[0].content == "제1장 총칙"

    by_key = {node.node_key: node for node in nodes}
    assert by_key["0002001-00"].level == 6
    assert by_key["0002001-00"].number == ""
    assert by_key["0002001-00"].content == ""
    assert by_key["0002001-00-0200"].number == "2"
    assert by_key["0002001-00-0200-01"].number == "가"

    _assert_unique_node_keys(nodes)
    _assert_parent_keys_resolve(nodes)


def test_parse_phase_1_decree_structure_nodes() -> None:
    nodes = _sample_nodes("data/raw/eflaw/014159/277417/20251001.xml")

    assert len(nodes) == 138
    by_key = {node.node_key: node for node in nodes}
    assert by_key["0003001-00"].level == 6
    assert by_key["0003001-00-0200-01"].content.startswith("가.")
    assert by_key["0003001-00-0400"].number == "4"
    assert by_key["0003001-00-0400-01"].number == "가"
    assert by_key["0004001-00-0200-01"].parent_node_key == "0004001-00-0200"

    _assert_unique_node_keys(nodes)
    _assert_parent_keys_resolve(nodes)


def test_parse_osh_act_inline_branched_items() -> None:
    nodes = _sample_nodes("data/raw/eflaw/001766/283449/20260601.xml")
    by_key = {node.node_key: node for node in nodes}

    assert by_key["0049001-01-0302"].number == "3의2"
    assert by_key["0049001-01-0302"].content.startswith("3의2.")

    _assert_unique_node_keys(nodes)
    _assert_parent_keys_resolve(nodes)


def _sample_nodes(relative_path: str):
    doc = parse_doc(Path(relative_path))
    return parse_structure_nodes(doc)


def _assert_unique_node_keys(nodes) -> None:
    node_keys = [node.node_key for node in nodes]
    assert len(node_keys) == len(set(node_keys))


def _assert_parent_keys_resolve(nodes) -> None:
    seen: set[str] = set()
    for node in nodes:
        if node.parent_node_key is not None:
            assert node.parent_node_key in seen
        seen.add(node.node_key)
