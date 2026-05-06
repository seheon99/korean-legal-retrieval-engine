"""CLI entry point.

Usage (from repo root):

    PYTHONPATH=src python -m ingest --raw-dir data/raw

Reads `DATABASE_URL` from the environment unless `--db-url` is given.
"""

from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path

from .populate import run


def main() -> None:
    parser = argparse.ArgumentParser(prog="ingest", description=__doc__)
    parser.add_argument(
        "--raw-dir",
        type=Path,
        default=Path("data/raw"),
        help="root of the canonical data/raw/eflaw/{law_id}/{mst}/{efYd}.xml store",
    )
    parser.add_argument(
        "--db-url",
        default=os.environ.get("DATABASE_URL"),
        help="psycopg DSN; falls back to $DATABASE_URL",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="DEBUG-level logging"
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )
    run(args.raw_dir, dsn=args.db_url)


if __name__ == "__main__":
    main()
