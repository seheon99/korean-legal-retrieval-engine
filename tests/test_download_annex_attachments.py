import importlib.util
import sys
import types
from pathlib import Path
from typing import Any

import pytest


sys.modules.setdefault("psycopg", types.SimpleNamespace())

_SCRIPT_PATH = (
    Path(__file__).resolve().parents[1] / "scripts" / "download_annex_attachments.py"
)
_SPEC = importlib.util.spec_from_file_location("download_annex_attachments", _SCRIPT_PATH)
assert _SPEC is not None
assert _SPEC.loader is not None
downloader = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = downloader
_SPEC.loader.exec_module(downloader)


def _row(
    attachment_id: int,
    attachment_type: str,
    *,
    annex_key: str = "000100E",
) -> Any:
    return downloader.AttachmentRow(
        attachment_id=attachment_id,
        law_id="014159",
        mst=277417,
        annex_key=annex_key,
        annex_number="1",
        annex_branch_number=None,
        attachment_type=attachment_type,
        source_attachment_url=f"/LSW/flDownload.do?flSeq={attachment_id}",
        source_filename=f"{annex_key}.{attachment_type}",
        stored_file_path=None,
        checksum_sha256=None,
    )


def test_default_retention_prefers_pdf_over_hwp(monkeypatch: pytest.MonkeyPatch) -> None:
    attempts: list[str] = []

    def fake_download_or_skip_row(*args: Any, **kwargs: Any) -> str:
        row = args[1]
        attempts.append(row.attachment_type)
        return "skipped"

    monkeypatch.setattr(downloader, "_download_or_skip_row", fake_download_or_skip_row)

    stats = downloader._download_pdf_default_rows(
        object(),
        [_row(1, "hwp"), _row(2, "pdf")],
        storage_root=Path("data/annexes"),
        base_url="https://www.law.go.kr",
        law_go_kr_oc=None,
    )

    assert attempts == ["pdf"]
    assert stats.downloaded == 0
    assert stats.skipped == 1
    assert stats.selected == 1


def test_default_retention_falls_back_to_hwp_when_pdf_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempts: list[str] = []

    def fake_download_or_skip_row(*args: Any, **kwargs: Any) -> str:
        row = args[1]
        attempts.append(row.attachment_type)
        if row.attachment_type == "pdf":
            raise downloader.DownloadUnavailableError("invalid PDF download")
        return "downloaded"

    monkeypatch.setattr(downloader, "_download_or_skip_row", fake_download_or_skip_row)

    stats = downloader._download_pdf_default_rows(
        object(),
        [_row(1, "hwp"), _row(2, "pdf")],
        storage_root=Path("data/annexes"),
        base_url="https://www.law.go.kr",
        law_go_kr_oc=None,
    )

    assert attempts == ["pdf", "hwp"]
    assert stats.downloaded == 1
    assert stats.skipped == 0
    assert stats.selected == 2


def test_invalid_pdf_shape_is_unavailable(tmp_path: Path) -> None:
    html_file = tmp_path / "not.pdf"
    html_file.write_bytes(b"<html>not a pdf</html>")

    with pytest.raises(downloader.DownloadUnavailableError):
        downloader._assert_download_shape(
            html_file,
            "pdf",
            "https://www.law.go.kr/LSW/flDownload.do?flSeq=1",
        )
