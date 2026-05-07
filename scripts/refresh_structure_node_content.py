#!/usr/bin/env python3
"""Refresh stored structure_nodes content/content_hash from retained raw XML.

Use when parser normalization changes but legal_documents.content_hash
still matches the raw XML, so the normal idempotent ingest path correctly
skips the existing document row.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any

from ingest.parse import discover, parse_doc, parse_structure_nodes


def main() -> int:
    args = _parse_args()
    dsn = args.db_url or os.environ.get("DATABASE_URL")
    if not dsn:
        raise SystemExit("DATABASE_URL not set; pass --db-url or export it.")

    import psycopg

    updated = 0
    with psycopg.connect(dsn) as conn:
        with conn.transaction():
            for xml_path in discover(args.raw_dir):
                doc = parse_doc(xml_path)
                doc_id = _doc_id(conn, doc.law_id, doc.mst, doc.effective_date)
                if doc_id is None:
                    continue
                for node in parse_structure_nodes(doc):
                    updated += _update_structure_node(conn, doc_id, node)

    print(f"updated_structure_nodes={updated}")
    return 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--raw-dir",
        type=Path,
        default=Path("data/raw"),
        help="root of the data/raw/eflaw/{law_id}/{mst}/{efYd}.xml store",
    )
    parser.add_argument(
        "--db-url",
        default=os.environ.get("DATABASE_URL"),
        help="psycopg DSN; falls back to $DATABASE_URL",
    )
    return parser.parse_args()


def _doc_id(conn: Any, law_id: str, mst: int, effective_date) -> int | None:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT doc_id
            FROM legal_documents
            WHERE law_id = %s
              AND mst = %s
              AND effective_date = %s
            """,
            (law_id, mst, effective_date),
        )
        row = cur.fetchone()
    return None if row is None else row[0]


def _update_structure_node(conn: Any, doc_id: int, node) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE structure_nodes
            SET content = %s,
                content_hash = %s
            WHERE doc_id = %s
              AND node_key = %s
              AND (
                content IS DISTINCT FROM %s
                OR content_hash IS DISTINCT FROM %s
              )
            """,
            (
                node.content,
                node.content_hash,
                doc_id,
                node.node_key,
                node.content,
                node.content_hash,
            ),
        )
        return cur.rowcount


if __name__ == "__main__":
    raise SystemExit(main())
