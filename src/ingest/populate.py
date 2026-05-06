"""Three-phase ingestion orchestrator (ADR-009 population rule).

Phase 1 — 법률    : parent_doc_id = NULL.
Phase 2 — 대통령령: lookup parent Act via title-strip + UNIQUE INDEX.
Phase 3 — 총리령/부령: parent_doc_id = NULL (ADR-009 patch #5
                       defers 부령 제1조 delegation parsing).

Children-table inserts are intentionally incremental. `structure_nodes`,
`supplementary_provisions`, `annexes`, `annex_attachments`, `forms`, and
`form_attachments` are implemented for the Phase-1 source layer.
"""

from __future__ import annotations

import logging
import os
from collections import defaultdict
from datetime import datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

import psycopg
from psycopg import Connection

from .parse import (
    discover,
    parse_annex_attachments,
    parse_annexes,
    parse_doc,
    parse_form_attachments,
    parse_forms,
    parse_structure_nodes,
    parse_supplementary_provisions,
)
from .records import Document, DocType


logger = logging.getLogger(__name__)

PHASE_ORDER: tuple[DocType, ...] = ("법률", "대통령령", "총리령", "부령")
DECREE_SUFFIX = " 시행령"
KST = ZoneInfo("Asia/Seoul")


class ContentMismatchError(Exception):
    """Same canonical source identity exists with a different `content_hash`.

    ADR-020 identity is `(law_id, mst, effective_date)`. A mismatch for
    that identity is source drift or local corruption, not an amendment.
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
            docs = sorted(
                by_type.get(doc_type, []),
                key=lambda doc: (doc.effective_date, doc.law_id, doc.mst),
            )
            if not docs:
                continue
            logger.info("phase %s: %d doc(s)", doc_type, len(docs))
            with conn.transaction():
                for doc in docs:
                    if _skip_if_present(conn, doc):
                        continue
                    effective_at = _effective_at(doc)
                    parent_doc_id = _resolve_parent(conn, doc)
                    superseded_doc_ids = _supersede_existing_heads(
                        conn, doc, effective_at
                    )
                    new_id = _insert_legal_document(
                        conn, doc, parent_doc_id, effective_at
                    )
                    _supersede_temporal_children(
                        conn, superseded_doc_ids, effective_at
                    )
                    _insert_children(conn, doc, new_id, effective_at)


def _skip_if_present(conn: Connection, doc: Document) -> bool:
    """Idempotent re-ingest for ADR-020 source-row identity.

    Match → no-op (don't INSERT, don't recurse into children).
    Mismatch → ContentMismatchError.
    Absent → False (caller proceeds with INSERT).
    """
    with conn.cursor() as cur:
        cur.execute(
            "SELECT doc_id, content_hash FROM legal_documents "
            "WHERE law_id = %s AND mst = %s AND effective_date = %s",
            (doc.law_id, doc.mst, doc.effective_date),
        )
        row = cur.fetchone()
    if row is None:
        return False
    existing_id, existing_hash = row
    if existing_hash == doc.content_hash:
        logger.info(
            "skip law_id=%s mst=%d effective_date=%s (%s, doc_id=%d) — "
            "content_hash match",
            doc.law_id, doc.mst, doc.effective_date, doc.title, existing_id,
        )
        return True
    raise ContentMismatchError(
        f"law_id={doc.law_id} mst={doc.mst} effective_date={doc.effective_date} "
        f"({doc.title!r}) exists with different content_hash; "
        f"existing={existing_hash[:12]}…, incoming={doc.content_hash[:12]}…. "
        f"ADR-020 source identity mismatch."
    )


def _effective_at(doc: Document) -> datetime:
    return datetime.combine(doc.effective_date, time.min, tzinfo=KST)


def _supersede_existing_heads(
    conn: Connection, doc: Document, incoming_effective_at: datetime
) -> list[int]:
    sql = """
        UPDATE legal_documents
        SET is_head = FALSE,
            superseded_at = %s,
            updated_at = NOW()
        WHERE law_id = %s
          AND is_head = TRUE
        RETURNING doc_id
    """
    with conn.cursor() as cur:
        cur.execute(sql, (incoming_effective_at, doc.law_id))
        rows = cur.fetchall()
    superseded_doc_ids = [row[0] for row in rows]
    if superseded_doc_ids:
        logger.info(
            "superseded %d legal_document head row(s) for law_id=%s at %s",
            len(superseded_doc_ids),
            doc.law_id,
            incoming_effective_at.isoformat(),
        )
    return superseded_doc_ids


def _supersede_temporal_children(
    conn: Connection, doc_ids: list[int], incoming_effective_at: datetime
) -> None:
    if not doc_ids:
        return

    for table in ("structure_nodes", "annexes", "forms"):
        sql = f"""
            UPDATE {table}
            SET is_head = FALSE,
                superseded_at = %s,
                updated_at = NOW()
            WHERE doc_id = ANY(%s::bigint[])
              AND is_head = TRUE
        """
        with conn.cursor() as cur:
            cur.execute(sql, (incoming_effective_at, doc_ids))
            logger.info(
                "superseded %d %s row(s) under doc_id(s)=%s",
                cur.rowcount,
                table,
                doc_ids,
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
                "WHERE title = %s AND doc_type = '법률' AND is_head = TRUE",
                (act_title,),
            )
            row = cur.fetchone()
        if row is None:
            raise LookupError(
                f"No head Act titled {act_title!r} for Decree "
                f"{doc.title!r}; ADR-009 Act-before-Decree ordering violated."
            )
        return row[0]

    # 총리령 / 부령 — deferred per ADR-009 patch #5.
    return None


def _insert_legal_document(
    conn: Connection,
    doc: Document,
    parent_doc_id: int | None,
    effective_at: datetime,
) -> int:
    sql = """
        INSERT INTO legal_documents (
          parent_doc_id, law_id, mst, title, title_abbrev, law_number,
          doc_type, doc_type_code, amendment_type, enacted_date,
          effective_date, competent_authority, competent_authority_code,
          structure_code, legislation_reason, source_url, content_hash,
          effective_at, superseded_at, is_head
        ) VALUES (
          %(parent_doc_id)s, %(law_id)s, %(mst)s, %(title)s,
          %(title_abbrev)s, %(law_number)s, %(doc_type)s,
          %(doc_type_code)s, %(amendment_type)s, %(enacted_date)s,
          %(effective_date)s, %(competent_authority)s,
          %(competent_authority_code)s, %(structure_code)s,
          %(legislation_reason)s, %(source_url)s, %(content_hash)s,
          %(effective_at)s, NULL, TRUE
        )
        RETURNING doc_id
    """
    params = doc.model_dump(exclude={"xml_path"})
    params["parent_doc_id"] = parent_doc_id
    params["effective_at"] = effective_at
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


def _insert_children(
    conn: Connection, doc: Document, doc_id: int, effective_at: datetime
) -> None:
    """Insert parsed child rows for `doc`."""
    _insert_structure_nodes(conn, doc, doc_id, effective_at)
    _insert_supplementary_provisions(conn, doc, doc_id)
    annex_ids = _insert_annexes(conn, doc, doc_id, effective_at)
    _insert_annex_attachments(conn, doc, annex_ids)
    form_ids = _insert_forms(conn, doc, doc_id, effective_at)
    _insert_form_attachments(conn, doc, form_ids)


def _insert_structure_nodes(
    conn: Connection, doc: Document, doc_id: int, effective_at: datetime
) -> None:
    nodes = parse_structure_nodes(doc)
    node_ids: dict[str, int] = {}
    sql = """
        INSERT INTO structure_nodes (
          doc_id, parent_id, level, node_key, number, title, content,
          sort_key, effective_date, is_changed, source_url, content_hash,
          effective_at, superseded_at, is_head
        ) VALUES (
          %(doc_id)s, %(parent_id)s, %(level)s, %(node_key)s, %(number)s,
          %(title)s, %(content)s, %(sort_key)s, %(effective_date)s,
          %(is_changed)s, %(source_url)s, %(content_hash)s,
          %(effective_at)s, NULL, TRUE
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
            params["effective_at"] = effective_at
            cur.execute(sql, params)
            row = cur.fetchone()
            assert row is not None
            node_ids[node.node_key] = row[0]

    logger.info(
        "inserted %d structure_node row(s) for doc_id=%d (%s)",
        len(nodes), doc_id, doc.title,
    )


def _insert_supplementary_provisions(
    conn: Connection, doc: Document, doc_id: int
) -> None:
    provisions = parse_supplementary_provisions(doc)
    sql = """
        INSERT INTO supplementary_provisions (
          doc_id, provision_key, promulgated_date, promulgation_number, content
        ) VALUES (
          %(doc_id)s, %(provision_key)s, %(promulgated_date)s,
          %(promulgation_number)s, %(content)s
        )
    """
    with conn.cursor() as cur:
        for provision in provisions:
            params = provision.model_dump()
            params["doc_id"] = doc_id
            cur.execute(sql, params)

    logger.info(
        "inserted %d supplementary_provision row(s) for doc_id=%d (%s)",
        len(provisions),
        doc_id,
        doc.title,
    )


def _insert_annexes(
    conn: Connection, doc: Document, doc_id: int, effective_at: datetime
) -> dict[str, int]:
    annexes = parse_annexes(doc)
    annex_ids: dict[str, int] = {}
    sql = """
        INSERT INTO annexes (
          doc_id, annex_key, number, branch_number, title, content_text,
          content_format, source_url, content_hash,
          effective_at, superseded_at, is_head
        ) VALUES (
          %(doc_id)s, %(annex_key)s, %(number)s, %(branch_number)s,
          %(title)s, %(content_text)s, %(content_format)s, %(source_url)s,
          %(content_hash)s, %(effective_at)s, NULL, TRUE
        )
        RETURNING annex_id
    """
    with conn.cursor() as cur:
        for annex in annexes:
            params = annex.model_dump()
            params["doc_id"] = doc_id
            params["effective_at"] = effective_at
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


def _insert_forms(
    conn: Connection, doc: Document, doc_id: int, effective_at: datetime
) -> dict[str, int]:
    forms = parse_forms(doc)
    form_ids: dict[str, int] = {}
    sql = """
        INSERT INTO forms (
          doc_id, form_key, number, branch_number, title, source_url,
          effective_at, superseded_at, is_head
        ) VALUES (
          %(doc_id)s, %(form_key)s, %(number)s, %(branch_number)s,
          %(title)s, %(source_url)s, %(effective_at)s, NULL, TRUE
        )
        RETURNING form_id
    """
    with conn.cursor() as cur:
        for form in forms:
            params = form.model_dump()
            params["doc_id"] = doc_id
            params["effective_at"] = effective_at
            cur.execute(sql, params)
            row = cur.fetchone()
            assert row is not None
            form_ids[form.form_key] = row[0]

    logger.info(
        "inserted %d form row(s) for doc_id=%d (%s)",
        len(forms),
        doc_id,
        doc.title,
    )
    return form_ids


def _insert_form_attachments(
    conn: Connection, doc: Document, form_ids: dict[str, int]
) -> None:
    attachments = parse_form_attachments(doc)
    sql = """
        INSERT INTO form_attachments (
          form_id, attachment_type, source_attachment_url, source_filename,
          stored_file_path, checksum_sha256, fetched_at
        ) VALUES (
          %(form_id)s, %(attachment_type)s, %(source_attachment_url)s,
          %(source_filename)s, %(stored_file_path)s, %(checksum_sha256)s,
          %(fetched_at)s
        )
    """
    with conn.cursor() as cur:
        for attachment in attachments:
            form_id = form_ids.get(attachment.form_key)
            if form_id is None:
                raise LookupError(
                    f"Form {attachment.form_key!r} not inserted before "
                    f"attachment ({doc.title}, mst={doc.mst})"
                )
            params = attachment.model_dump(exclude={"form_key"})
            params["form_id"] = form_id
            cur.execute(sql, params)

    logger.info(
        "inserted %d form_attachment row(s) for %s",
        len(attachments),
        doc.title,
    )
