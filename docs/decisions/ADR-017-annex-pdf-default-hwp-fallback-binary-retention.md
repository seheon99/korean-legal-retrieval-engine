# ADR-017 — PDF-default annex binary retention with HWP fallback

- **Status**: Accepted
- **Date**: 2026-05-05
- **Context layer**: Statute (성문규범) ingestion pipeline —
  annex attachment binary retention policy
- **Supersedes / amends**:
  - **ADR-016 (Accepted)** — narrows default Phase-1 annex binary
    retention from HWP/PDF/image to PDF-first with HWP fallback.
- **Depends on / aligned with**:
  - **ADR-014 (Accepted)** — keep source attachment rows as provenance;
    attachments are not retrieval source rows.
  - **ADR-016 (Accepted)** — validated that HWP, PDF, and rendered image
    files can all be downloaded and stored under `data/annexes/`.
- **Resolves**:
  - Whether Phase 1 must retain all HWP/PDF/image binaries.
  - What the downloader's default attachment preference order should be.
  - Which attachment row should carry application-owned binary retention
    fields.
- **Out of scope (not decided here)**:
  1. Form attachment binary retention.
  2. OCR / table extraction from PDFs.
  3. Object storage / S3.
  4. Legal-display UI requirements that might later need original HWP or
     image files.

## Context

ADR-016 implemented full annex binary retention for the Phase-1 Decree:

- 5 HWP files
- 5 PDF files
- 11 GIF image files

Review showed the retained artifacts represent the same annex surface:

- PDF page counts are `2, 2, 4, 2, 1`.
- The image filename counts per annex are also `2, 2, 4, 2, 1`.
- The PDFs expose the full rendered annex pages and are easy to inspect
  with standard tools.
- The HWP files are useful as upstream originals but add no Phase-1
  retrieval value when PDF is available.
- The GIF rows are page renderings of the same annex surface.

Retaining all three formats creates redundant network work, storage, DB
state, and checksum maintenance without improving the Phase-1 retrieval
walking skeleton.

## Decision

For Phase 1, **PDF is the default local binary retention format for
annexes**.

HWP is the fallback binary format when PDF retention is unavailable or
invalid. Image files are not a fallback retention format.

Fallback to HWP only when one of these conditions is true for an annex:

- no PDF attachment row exists
- the PDF row has no usable `source_attachment_url`
- PDF download fails after the normal retry behavior
- the downloaded PDF is empty or fails basic file verification

When PDF retention succeeds, do not retain HWP or image binaries.

Keep `annex_attachments` rows for HWP, PDF, and image as source
provenance. Do not delete source attachment rows.

Only the selected retained format should have application-owned binary
retention fields populated. For the normal path, that is the PDF row:

```sql
attachment_type = 'pdf'
AND stored_file_path IS NOT NULL
AND checksum_sha256 IS NOT NULL
AND fetched_at IS NOT NULL
```

If PDF retention falls back to HWP for a future annex, the HWP row becomes
the retained row for that annex:

```sql
attachment_type = 'hwp'
AND stored_file_path IS NOT NULL
AND checksum_sha256 IS NOT NULL
AND fetched_at IS NOT NULL
```

For the current Phase-1 corpus, all PDFs downloaded and verified
successfully. Therefore HWP and image rows remain valid provenance rows,
but their local storage fields should be `NULL`:

```sql
stored_file_path = NULL
checksum_sha256 = NULL
fetched_at = NULL
```

The downloader default changes from HWP/PDF/image retention to PDF-first
with HWP fallback:

```bash
python scripts/download_annex_attachments.py
```

Default behavior:

1. try PDF for each annex
2. retain the PDF when it succeeds
3. fallback to HWP only when PDF retention is unavailable or invalid
4. never retain images by default

Explicit operator selection remains possible:

```bash
python scripts/download_annex_attachments.py --types pdf
python scripts/download_annex_attachments.py --types hwp
python scripts/download_annex_attachments.py --types image
```

This keeps the capability for debugging or future extraction without
making redundant retention the default path.

## Options considered

| Option | Verdict |
|--------|---------|
| A. PDF-first required retention with HWP fallback; keep HWP/image source rows as provenance | **recommended** — preserves evidence while avoiding redundant binaries |
| B. Retain HWP/PDF/image for every annex | rejected — verified redundant for Phase 1 |
| C. Retain images only | rejected — page images are less convenient for text extraction and inspection than PDFs |
| D. Retain HWP only | rejected — HWP is a source office format, but Phase-1 tooling around PDF is simpler |
| E. SQL-delete HWP/image attachment rows | rejected — loses upstream provenance and disables HWP fallback |
| F. PDF-only with no fallback | rejected — HWP is useful when a future PDF is missing or invalid |

## Consequences

- Storage and download work normally drop from 21 files to 5 files for the
  Phase-1 Decree.
- `annex_attachments` remains a complete source-provenance table.
- Retrieval/chunking work can use `annexes.content_text` first and PDFs
  as the durable rendered binary fallback.
- HWP retention remains available as the fallback when PDF retention fails.
- Future image work is still possible by explicit `--types image`
  selection.

## Implementation requirements

1. Change the downloader default to PDF-first with HWP fallback.
2. Verify the default path stores PDF rows when PDFs are available.
3. Verify the fallback path stores HWP rows when PDF retention is
   unavailable or invalid.
