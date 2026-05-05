"""Three-phase ingestion orchestrator (ADR-009 population rule).

Phase 1 — 법률    : parent_doc_id = NULL.
Phase 2 — 대통령령: lookup parent Act via title-strip + UNIQUE INDEX.
Phase 3 — 총리령/부령: parent_doc_id = NULL (ADR-009 patch #5
                       defers 부령 제1조 delegation parsing).

Children-table inserts are intentionally incremental. `structure_nodes`,
`annexes`, and `annex_attachments` are implemented; supplementary
provisions and forms remain deferred parser passes.
"""

from __future__ import annotations

import logging
import os
from collections import defaultdict
from pathlib import Path

import psycopg
from psycopg import Connection

from .parse import (
    discover,
    parse_annex_attachments,
    parse_annexes,
    parse_doc,
    parse_structure_nodes,
)
from .records import Document, DocType


logger = logging.getLogger(__name__)

PHASE_ORDER: tuple[DocType, ...] = ("법률", "대통령령", "총리령", "부령")
DECREE_SUFFIX = " 시행령"


class ContentMismatchError(Exception):
    """Same MST exists with a different `content_hash` — substantive
    change that requires the (deferred) amendment-tracking flow.

    Fail-fast posture: silent overwrite would lose the prior version
    without setting `superseded_at` / `is_current=FALSE`. The
    amendment-track decision is its own ADR (TODO-5 territory) and
    not in scope here.
    """


def run(raw_dir: Path, *, dsn: str | None = None) -> None:
    """Walk `raw_dir`, parse all docs, then load in phase order."""
    dsn = dsn or os.environ.get("DATABASE_URL")
    if not dsn:
        raise SystemExit(
            "DATABASE_URL not set; pass --db-url or export it before running."
        )

    by_type: dict[DocType, list[Document]] = defaultdict(list)
    for path in discover(raw_dir):
        doc = parse_doc(path)
        by_type[doc.doc_type].append(doc)
        logger.info("parsed %s (%s, mst=%d)", doc.title, doc.doc_type, doc.mst)

    # One transaction per phase: Phase N's COMMIT must be visible to
    # Phase N+1's parent-lookup SELECT. Same connection, default
    # READ COMMITTED — visibility kicks in at COMMIT.
    with psycopg.connect(dsn) as conn:
        for doc_type in PHASE_ORDER:
            docs = by_type.get(doc_type, [])
            if not docs:
                continue
            logger.info("phase %s: %d doc(s)", doc_type, len(docs))
            with conn.transaction():
                for doc in docs:
                    if _skip_if_present(conn, doc):
                        continue
                    parent_doc_id = _resolve_parent(conn, doc)
                    new_id = _insert_legal_document(conn, doc, parent_doc_id)
                    _insert_children(conn, doc, new_id)


def _skip_if_present(conn: Connection, doc: Document) -> bool:
    """Idempotent re-ingest: True if a row with `doc.mst` already
    exists and its `content_hash` matches; raise on mismatch.

    Match → no-op (don't INSERT, don't recurse into children).
    Mismatch → ContentMismatchError (substantive change; out of scope).
    Absent → False (caller proceeds with INSERT).
    """
    with conn.cursor() as cur:
        cur.execute(
            "SELECT doc_id, content_hash FROM legal_documents WHERE mst = %s",
            (doc.mst,),
        )
        row = cur.fetchone()
    if row is None:
        return False
    existing_id, existing_hash = row
    if existing_hash == doc.content_hash:
        logger.info(
            "skip mst=%d (%s, doc_id=%d) — content_hash match",
            doc.mst, doc.title, existing_id,
        )
        return True
    raise ContentMismatchError(
        f"mst={doc.mst} ({doc.title!r}) exists with different content_hash; "
        f"existing={existing_hash[:12]}…, incoming={doc.content_hash[:12]}…. "
        f"Substantive change — amendment tracking is deferred (TODO-5)."
    )


def _resolve_parent(conn: Connection, doc: Document) -> int | None:
    """Apply the ADR-009 population rule — the load-bearing piece."""
    if doc.doc_type == "법률":
        return None

    if doc.doc_type == "대통령령":
        if not doc.title.endswith(DECREE_SUFFIX):
            raise ValueError(
                f"Decree title {doc.title!r} does not end in "
                f"{DECREE_SUFFIX!r}; cannot derive parent Act title."
            )
        act_title = doc.title[: -len(DECREE_SUFFIX)]
        with conn.cursor() as cur:
            cur.execute(
                "SELECT doc_id FROM legal_documents "
                "WHERE title = %s AND doc_type = '법률' AND is_current = TRUE",
                (act_title,),
            )
            row = cur.fetchone()
        if row is None:
            raise LookupError(
                f"No current Act titled {act_title!r} for Decree "
                f"{doc.title!r}; ADR-009 Act-before-Decree ordering violated."
            )
        return row[0]

    # 총리령 / 부령 — deferred per ADR-009 patch #5.
    return None


def _insert_legal_document(
    conn: Connection, doc: Document, parent_doc_id: int | None
) -> int:
    sql = """
        INSERT INTO legal_documents (
          parent_doc_id, law_id, mst, title, title_abbrev, law_number,
          doc_type, doc_type_code, amendment_type, enacted_date,
          effective_date, competent_authority, competent_authority_code,
          structure_code, legislation_reason, source_url, content_hash,
          is_current
        ) VALUES (
          %(parent_doc_id)s, %(law_id)s, %(mst)s, %(title)s,
          %(title_abbrev)s, %(law_number)s, %(doc_type)s,
          %(doc_type_code)s, %(amendment_type)s, %(enacted_date)s,
          %(effective_date)s, %(competent_authority)s,
          %(competent_authority_code)s, %(structure_code)s,
          %(legislation_reason)s, %(source_url)s, %(content_hash)s,
          TRUE
        )
        RETURNING doc_id
    """
    params = doc.model_dump(exclude={"xml_path"})
    params["parent_doc_id"] = parent_doc_id
    with conn.cursor() as cur:
        cur.execute(sql, params)
        row = cur.fetchone()
    assert row is not None  # RETURNING always yields one row on success
    doc_id = row[0]
    logger.info(
        "inserted doc_id=%d (%s, parent_doc_id=%s)",
        doc_id, doc.title, parent_doc_id,
    )
    return doc_id


def _insert_children(conn: Connection, doc: Document, doc_id: int) -> None:
    """Insert parsed child rows for `doc`.

    Forms remain intentionally out of scope until a form-bearing corpus
    enters Phase-1 scope.
    """
    _insert_structure_nodes(conn, doc, doc_id)
    annex_ids = _insert_annexes(conn, doc, doc_id)
    _insert_annex_attachments(conn, doc, annex_ids)


def _insert_structure_nodes(conn: Connection, doc: Document, doc_id: int) -> None:
    nodes = parse_structure_nodes(doc)
    node_ids: dict[str, int] = {}
    sql = """
        INSERT INTO structure_nodes (
          doc_id, parent_id, level, node_key, number, title, content,
          sort_key, effective_date, is_changed, source_url, content_hash,
          is_current
        ) VALUES (
          %(doc_id)s, %(parent_id)s, %(level)s, %(node_key)s, %(number)s,
          %(title)s, %(content)s, %(sort_key)s, %(effective_date)s,
          %(is_changed)s, %(source_url)s, %(content_hash)s, TRUE
        )
        RETURNING node_id
    """
    with conn.cursor() as cur:
        for node in nodes:
            parent_id = None
            if node.parent_node_key is not None:
                parent_id = node_ids.get(node.parent_node_key)
                if parent_id is None:
                    raise LookupError(
                        f"Parent node_key {node.parent_node_key!r} not inserted "
                        f"before child {node.node_key!r} ({doc.title}, mst={doc.mst})"
                    )
            params = node.model_dump(exclude={"parent_node_key"})
            params["doc_id"] = doc_id
            params["parent_id"] = parent_id
            cur.execute(sql, params)
            row = cur.fetchone()
            assert row is not None
            node_ids[node.node_key] = row[0]

    logger.info(
        "inserted %d structure_node row(s) for doc_id=%d (%s)",
        len(nodes), doc_id, doc.title,
    )


def _insert_annexes(conn: Connection, doc: Document, doc_id: int) -> dict[str, int]:
    annexes = parse_annexes(doc)
    annex_ids: dict[str, int] = {}
    sql = """
        INSERT INTO annexes (
          doc_id, annex_key, number, branch_number, title, content_text,
          content_format, source_url, content_hash, is_current
        ) VALUES (
          %(doc_id)s, %(annex_key)s, %(number)s, %(branch_number)s,
          %(title)s, %(content_text)s, %(content_format)s, %(source_url)s,
          %(content_hash)s, TRUE
        )
        RETURNING annex_id
    """
    with conn.cursor() as cur:
        for annex in annexes:
            params = annex.model_dump()
            params["doc_id"] = doc_id
            cur.execute(sql, params)
            row = cur.fetchone()
            assert row is not None
            annex_ids[annex.annex_key] = row[0]

    logger.info(
        "inserted %d annex row(s) for doc_id=%d (%s)",
        len(annexes), doc_id, doc.title,
    )
    return annex_ids


def _insert_annex_attachments(
    conn: Connection, doc: Document, annex_ids: dict[str, int]
) -> None:
    attachments = parse_annex_attachments(doc)
    sql = """
        INSERT INTO annex_attachments (
          annex_id, attachment_type, source_attachment_url, source_filename,
          stored_file_path, checksum_sha256, fetched_at
        ) VALUES (
          %(annex_id)s, %(attachment_type)s, %(source_attachment_url)s,
          %(source_filename)s, %(stored_file_path)s, %(checksum_sha256)s,
          %(fetched_at)s
        )
    """
    with conn.cursor() as cur:
        for attachment in attachments:
            annex_id = annex_ids.get(attachment.annex_key)
            if annex_id is None:
                raise LookupError(
                    f"Annex {attachment.annex_key!r} not inserted before "
                    f"attachment ({doc.title}, mst={doc.mst})"
                )
            params = attachment.model_dump(exclude={"annex_key"})
            params["annex_id"] = annex_id
            cur.execute(sql, params)

    logger.info(
        "inserted %d annex_attachment row(s) for %s",
        len(attachments), doc.title,
    )
