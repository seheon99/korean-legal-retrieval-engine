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
import re
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from html.parser import HTMLParser
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
    annex_number: str
    annex_branch_number: str | None
    attachment_type: str
    source_attachment_url: str | None
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
        discovered_image_urls = _discover_missing_image_urls(
            rows,
            base_url=args.base_url,
            law_go_kr_oc=law_go_kr_oc,
        )
        downloaded = 0
        skipped = 0

        for row in rows:
            source_attachment_url = row.source_attachment_url
            if source_attachment_url is None:
                source_attachment_url = discovered_image_urls.get(row.attachment_id)
            if source_attachment_url is None:
                raise ValueError(
                    f"attachment_id={row.attachment_id}: source_attachment_url "
                    "missing and no verified discovery result exists"
                )

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
                source_attachment_url,
                base_url=args.base_url,
                law_go_kr_oc=law_go_kr_oc,
            )
            checksum = _download_to_target(request_url, target)
            _update_row(
                conn,
                row.attachment_id,
                repo_relative_path,
                checksum,
                source_attachment_url=source_attachment_url,
            )
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
          a.number,
          a.branch_number,
          aa.attachment_type,
          aa.source_attachment_url,
          aa.source_filename,
          aa.stored_file_path,
          aa.checksum_sha256
        FROM annex_attachments aa
        JOIN annexes a ON a.annex_id = aa.annex_id
        JOIN legal_documents ld ON ld.doc_id = a.doc_id
        WHERE aa.attachment_type = ANY(%s)
          AND (
            aa.source_attachment_url IS NOT NULL
            OR aa.attachment_type = 'image'
          )
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
            annex_number=row[4],
            annex_branch_number=row[5],
            attachment_type=row[6],
            source_attachment_url=row[7],
            source_filename=row[8],
            stored_file_path=row[9],
            checksum_sha256=row[10],
        )
        for row in rows
    ]


def _discover_missing_image_urls(
    rows: list[AttachmentRow], *, base_url: str, law_go_kr_oc: str | None
) -> dict[int, str]:
    image_rows = [
        row
        for row in rows
        if row.attachment_type == "image" and row.source_attachment_url is None
    ]
    if not image_rows:
        return {}
    if not law_go_kr_oc:
        raise ValueError("LAW_GO_KR_OC is required for rendered image URL discovery")

    by_annex: dict[tuple[str, int, str], list[AttachmentRow]] = {}
    for row in image_rows:
        by_annex.setdefault((row.law_id, row.mst, row.annex_key), []).append(row)

    discovered: dict[int, str] = {}
    for annex_rows in by_annex.values():
        annex_rows.sort(key=lambda row: row.attachment_id)
        urls = _discover_image_urls_for_annex(
            annex_rows[0], base_url=base_url, law_go_kr_oc=law_go_kr_oc
        )
        if len(urls) != len(annex_rows):
            raise ValueError(
                f"{annex_rows[0].annex_key}: rendered image URL count "
                f"{len(urls)} does not match DB image row count {len(annex_rows)}"
            )
        for row, url in zip(annex_rows, urls, strict=True):
            discovered[row.attachment_id] = url
            print(
                f"discovered image URL attachment_id={row.attachment_id}: "
                f"{row.source_filename} -> {url}"
            )
    return discovered


def _discover_image_urls_for_annex(
    row: AttachmentRow, *, base_url: str, law_go_kr_oc: str
) -> list[str]:
    branch_number = row.annex_branch_number or "0"
    params = {
        "OC": law_go_kr_oc,
        "target": "law",
        "MST": str(row.mst),
        "type": "HTML",
        "mobileYn": "Y",
        "BD": "ON",
        "BT": "1",
        "BN": row.annex_number,
        "BG": branch_number,
    }
    html = _fetch_text(
        f"{base_url}/DRF/lawService.do?{urllib.parse.urlencode(params)}"
    )
    popup_url = _extract_location_href(html, base_url=base_url)
    popup_parts = urllib.parse.urlsplit(popup_url)
    popup_query = urllib.parse.parse_qs(popup_parts.query)
    byl_seq = _single_query_value(popup_query, "bylSeq", popup_url)

    info_html = _post_text(
        urllib.parse.urljoin(base_url, "/LSW/lsBylInfoR.do"),
        {
            "bylSeq": byl_seq,
            "lsiSeq": str(row.mst),
            "vSct": "",
            "efYd": "",
        },
    )
    option_values = _extract_selected_option_values(info_html)
    selected = _select_rendered_annex_option(option_values, row)

    contents_html = _post_text(
        urllib.parse.urljoin(base_url, "/LSW/lsBylContentsInfoR.do"),
        {
            "lsiSeq": selected[0],
            "bylNo": selected[1],
            "bylBrNo": selected[2],
            "bylClsCd": selected[3],
            "lsId": row.law_id,
            "bylSeq": selected[0],
            "bylEfYd": selected[4],
            "vSct": "",
            "directYn": "",
        },
    )
    parser = _ImageSrcParser()
    parser.feed(contents_html)
    urls = [_clean_source_url(src, base_url=base_url) for src in parser.image_srcs]
    if not urls:
        raise ValueError(f"{row.annex_key}: no rendered image URLs discovered")
    return urls


def _fetch_text(url: str) -> str:
    with urllib.request.urlopen(url, timeout=60) as response:
        return response.read().decode("utf-8", "replace")


def _post_text(url: str, data: dict[str, str]) -> str:
    request = urllib.request.Request(
        url,
        data=urllib.parse.urlencode(data).encode(),
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read().decode("utf-8", "replace")


def _extract_location_href(html: str, *, base_url: str) -> str:
    match = re.search(r"location\.href\s*=\s*['\"]([^'\"]+)['\"]", html)
    if match is None:
        raise ValueError("rendered lawService HTML did not expose location.href")
    return urllib.parse.urljoin(base_url, match.group(1))


def _single_query_value(
    query: dict[str, list[str]], key: str, source_url: str
) -> str:
    values = query.get(key)
    if not values or len(values) != 1 or not values[0]:
        raise ValueError(f"{source_url}: expected one query value for {key}")
    return values[0]


def _extract_selected_option_values(html: str) -> list[tuple[str, str, str, str, str]]:
    values: list[tuple[str, str, str, str, str]] = []
    for value in re.findall(r"<option\s+value=\"([^\"]+)\"", html):
        parts = tuple(value.split(","))
        if len(parts) == 5:
            values.append(parts)  # type: ignore[arg-type]
    if not values:
        raise ValueError("lsBylInfoR response did not expose annex option values")
    return values


def _select_rendered_annex_option(
    values: list[tuple[str, str, str, str, str]], row: AttachmentRow
) -> tuple[str, str, str, str, str]:
    number = int(row.annex_number)
    branch_number = int(row.annex_branch_number or "0")
    for value in values:
        if int(value[1]) == number and int(value[2]) == branch_number:
            return value
    raise ValueError(f"{row.annex_key}: no rendered option matched number/branch")


class _ImageSrcParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.image_srcs: list[str] = []

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        if tag.lower() != "img":
            return
        attrs_dict = {key.lower(): value for key, value in attrs}
        src = attrs_dict.get("src")
        if src is None:
            return
        if "/LSW/flDownload.do" not in src:
            return
        self.image_srcs.append(src)


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


def _clean_source_url(source_url: str, *, base_url: str) -> str:
    absolute = urllib.parse.urljoin(base_url, source_url)
    parts = urllib.parse.urlsplit(absolute)
    query = [
        (key, value)
        for key, value in urllib.parse.parse_qsl(parts.query, keep_blank_values=True)
        if key != "OC"
    ]
    clean = urllib.parse.urlunsplit(
        parts._replace(query=urllib.parse.urlencode(query))
    )
    base_parts = urllib.parse.urlsplit(base_url)
    if parts.scheme == base_parts.scheme and parts.netloc == base_parts.netloc:
        path_parts = urllib.parse.urlsplit(clean)
        suffix = path_parts.path
        if path_parts.query:
            suffix = f"{suffix}?{path_parts.query}"
        return suffix
    return clean


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
    conn: psycopg.Connection,
    attachment_id: int,
    stored_file_path: str,
    checksum: str,
    *,
    source_attachment_url: str,
) -> None:
    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE annex_attachments
                SET stored_file_path = %s,
                    checksum_sha256 = %s,
                    fetched_at = NOW(),
                    source_attachment_url = COALESCE(source_attachment_url, %s)
                WHERE attachment_id = %s
                """,
                (stored_file_path, checksum, source_attachment_url, attachment_id),
            )


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
