#!/usr/bin/env python3
"""Download annex attachment binaries and update annex_attachments.

Stores files under data/annexes/{law_id}/{mst}/{annex_key}/{filename}
per ADR-016. OC may be used for the outbound request, but is never
persisted in the database.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

import psycopg


DEFAULT_BASE_URL = "https://www.law.go.kr"
DEFAULT_TYPES = ("hwp", "pdf")
VALID_TYPES = ("hwp", "pdf", "image")


@dataclass(frozen=True)
class AttachmentRow:
    attachment_id: int
    law_id: str
    mst: int
    annex_key: str
    attachment_type: str
    source_attachment_url: str
    source_filename: str
    stored_file_path: str | None
    checksum_sha256: str | None


def main() -> int:
    args = _parse_args()
    dsn = args.db_url or os.environ.get("DATABASE_URL")
    if not dsn:
        raise SystemExit("DATABASE_URL not set; pass --db-url or export it.")

    storage_root = Path(args.storage_root)
    law_go_kr_oc = os.environ.get("LAW_GO_KR_OC")

    with psycopg.connect(dsn) as conn:
        rows = _fetch_rows(conn, args.types)
        downloaded = 0
        skipped = 0

        for row in rows:
            target = _target_path(storage_root, row)
            repo_relative_path = target.as_posix()
            existing_path = (
                Path(row.stored_file_path) if row.stored_file_path is not None else None
            )

            if existing_path is not None and row.checksum_sha256 is not None:
                _assert_existing_file(existing_path, row.checksum_sha256, row)
                skipped += 1
                print(
                    f"skip attachment_id={row.attachment_id}: "
                    f"{existing_path.as_posix()} already matches checksum"
                )
                continue

            request_url = _request_url(
                row.source_attachment_url,
                base_url=args.base_url,
                law_go_kr_oc=law_go_kr_oc,
            )
            checksum = _download_to_target(request_url, target)
            _update_row(conn, row.attachment_id, repo_relative_path, checksum)
            downloaded += 1
            print(
                f"downloaded attachment_id={row.attachment_id}: "
                f"{repo_relative_path} sha256={checksum}"
            )

    print(f"done: downloaded={downloaded}, skipped={skipped}, selected={len(rows)}")
    return 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download annex attachment binaries per ADR-016."
    )
    parser.add_argument(
        "--db-url",
        default=os.environ.get("DATABASE_URL"),
        help="psycopg DSN; falls back to $DATABASE_URL",
    )
    parser.add_argument(
        "--storage-root",
        default="data/annexes",
        help="repo-relative output root; default: data/annexes",
    )
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help=f"base URL for relative source_attachment_url values; default: {DEFAULT_BASE_URL}",
    )
    parser.add_argument(
        "--types",
        nargs="+",
        default=list(DEFAULT_TYPES),
        choices=VALID_TYPES,
        help="attachment types to download; default: hwp pdf",
    )
    return parser.parse_args()


def _fetch_rows(conn: psycopg.Connection, types: list[str]) -> list[AttachmentRow]:
    sql = """
        SELECT
          aa.attachment_id,
          ld.law_id,
          ld.mst,
          a.annex_key,
          aa.attachment_type,
          aa.source_attachment_url,
          aa.source_filename,
          aa.stored_file_path,
          aa.checksum_sha256
        FROM annex_attachments aa
        JOIN annexes a ON a.annex_id = aa.annex_id
        JOIN legal_documents ld ON ld.doc_id = a.doc_id
        WHERE aa.attachment_type = ANY(%s)
          AND aa.source_attachment_url IS NOT NULL
          AND aa.source_filename IS NOT NULL
        ORDER BY ld.law_id, ld.mst, a.annex_key, aa.attachment_type, aa.attachment_id
    """
    with conn.cursor() as cur:
        cur.execute(sql, (types,))
        rows = cur.fetchall()
    return [
        AttachmentRow(
            attachment_id=row[0],
            law_id=row[1],
            mst=row[2],
            annex_key=row[3],
            attachment_type=row[4],
            source_attachment_url=row[5],
            source_filename=row[6],
            stored_file_path=row[7],
            checksum_sha256=row[8],
        )
        for row in rows
    ]


def _target_path(storage_root: Path, row: AttachmentRow) -> Path:
    filename = _safe_basename(row.source_filename, row.attachment_id)
    return storage_root / row.law_id / str(row.mst) / row.annex_key / filename


def _safe_basename(filename: str, attachment_id: int) -> str:
    candidate = Path(filename)
    if (
        not filename
        or candidate.name != filename
        or filename in {".", ".."}
        or "/" in filename
        or "\\" in filename
    ):
        raise ValueError(
            f"attachment_id={attachment_id}: unsafe source_filename {filename!r}"
        )
    return filename


def _request_url(
    source_attachment_url: str, *, base_url: str, law_go_kr_oc: str | None
) -> str:
    url = urllib.parse.urljoin(base_url, source_attachment_url)
    if not law_go_kr_oc:
        return url

    parts = urllib.parse.urlsplit(url)
    query = urllib.parse.parse_qsl(parts.query, keep_blank_values=True)
    if not any(key == "OC" for key, _ in query):
        query.append(("OC", law_go_kr_oc))
    return urllib.parse.urlunsplit(
        parts._replace(query=urllib.parse.urlencode(query))
    )


def _assert_existing_file(path: Path, checksum_sha256: str, row: AttachmentRow) -> None:
    if not path.exists():
        raise FileNotFoundError(
            f"attachment_id={row.attachment_id}: DB points to missing file {path}"
        )
    actual = _sha256_file(path)
    if actual != checksum_sha256:
        raise ValueError(
            f"attachment_id={row.attachment_id}: checksum mismatch for {path}; "
            f"db={checksum_sha256}, actual={actual}"
        )
    path.chmod(0o644)


def _download_to_target(request_url: str, target: Path) -> str:
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{target.name}.", suffix=".tmp", dir=target.parent
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as f:
            try:
                with urllib.request.urlopen(request_url, timeout=60) as response:
                    while True:
                        chunk = response.read(1 << 16)
                        if not chunk:
                            break
                        f.write(chunk)
            except urllib.error.URLError as exc:
                raise RuntimeError(f"download failed: {request_url}") from exc

        if tmp_path.stat().st_size == 0:
            raise ValueError(f"empty download: {request_url}")

        checksum = _sha256_file(tmp_path)
        if target.exists():
            existing_checksum = _sha256_file(target)
            if existing_checksum != checksum:
                raise ValueError(
                    f"target exists with different checksum: {target}; "
                    f"existing={existing_checksum}, downloaded={checksum}"
                )
            tmp_path.unlink()
            target.chmod(0o644)
            return checksum

        tmp_path.replace(target)
        target.chmod(0o644)
        return checksum
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def _update_row(
    conn: psycopg.Connection, attachment_id: int, stored_file_path: str, checksum: str
) -> None:
    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE annex_attachments
                SET stored_file_path = %s,
                    checksum_sha256 = %s,
                    fetched_at = NOW()
                WHERE attachment_id = %s
                """,
                (stored_file_path, checksum, attachment_id),
            )


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
