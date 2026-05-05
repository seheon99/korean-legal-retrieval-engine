#!/usr/bin/env python3
"""Refresh stored annex content_text/content_hash from retained raw XML.

Use when parser normalization changes but legal_documents.content_hash
still matches the raw XML, so the normal idempotent ingest path correctly
skips the existing document row.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import psycopg

from ingest.parse import discover, parse_annexes, parse_doc


def main() -> int:
    args = _parse_args()
    dsn = args.db_url or os.environ.get("DATABASE_URL")
    if not dsn:
        raise SystemExit("DATABASE_URL not set; pass --db-url or export it.")

    updated = 0
    with psycopg.connect(dsn) as conn:
        with conn.transaction():
            for xml_path in discover(args.raw_dir):
                doc = parse_doc(xml_path)
                doc_id = _doc_id(conn, doc.mst)
                if doc_id is None:
                    continue
                for annex in parse_annexes(doc):
                    updated += _update_annex(conn, doc_id, annex)

    print(f"updated_annexes={updated}")
    return 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--raw-dir",
        type=Path,
        default=Path("data/raw"),
        help="root of the data/raw/{law_id}/{mst}.xml store",
    )
    parser.add_argument(
        "--db-url",
        default=os.environ.get("DATABASE_URL"),
        help="psycopg DSN; falls back to $DATABASE_URL",
    )
    return parser.parse_args()


def _doc_id(conn: psycopg.Connection, mst: int) -> int | None:
    with conn.cursor() as cur:
        cur.execute("SELECT doc_id FROM legal_documents WHERE mst = %s", (mst,))
        row = cur.fetchone()
    return None if row is None else row[0]


def _update_annex(conn: psycopg.Connection, doc_id: int, annex) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE annexes
            SET content_text = %s,
                content_hash = %s
            WHERE doc_id = %s
              AND annex_key = %s
              AND (
                content_text IS DISTINCT FROM %s
                OR content_hash IS DISTINCT FROM %s
              )
            """,
            (
                annex.content_text,
                annex.content_hash,
                doc_id,
                annex.annex_key,
                annex.content_text,
                annex.content_hash,
            ),
        )
        return cur.rowcount


if __name__ == "__main__":
    raise SystemExit(main())
