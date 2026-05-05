# ADR-016 — Annex attachment binary retention

- **Status**: Accepted
- **Date**: 2026-05-05
- **Context layer**: Statute (성문규범) ingestion pipeline —
  annex attachment binary download and retention
- **Resolves**:
  - Where downloaded annex attachment binaries are stored on disk.
  - When `annex_attachments.stored_file_path`, `checksum_sha256`, and
    `fetched_at` are populated.
  - How relative law.go.kr download links are resolved.
  - How the OC key may be used during download without polluting stored
    source URLs.
  - Whether Phase 1 downloads image attachments that currently have no
    source URL.
- **Depends on / aligned with**:
  - **ADR-011 (Accepted)** — raw XML is retained under `data/raw/` and
    gitignored.
  - **ADR-014 (Accepted)** — attachment rows preserve upstream source
    references separately from application-owned storage paths.
  - **ADR-015 (Accepted)** — post-freeze schema changes are ordered raw
    SQL migrations; this ADR requires no schema migration.
- **Out of scope (not decided here)**:
  1. Downloading form attachments.
  2. OCR or text extraction from downloaded binaries.
  3. Object storage / S3 layout.
  4. `attachment_blobs` or checksum-based deduplication.
  5. Unverified image download URL inference from law.go.kr internals.

## Context

ADR-014 intentionally inserted attachment-reference rows without
downloading binaries. The current Phase-1 Decree sample creates 21
`annex_attachments` rows:

- 5 HWP rows with `source_attachment_url`.
- 5 PDF rows with `source_attachment_url`.
- 11 image rows with `source_attachment_url = NULL` and only
  `source_filename`.

`stored_file_path` must mean "the application-controlled file exists
here." It must not be populated merely because a future target path is
known.

The user selected the filesystem layout:

```text
./data/annexes/{law_id}/{mst}/{annex_key}/{filename}
```

This mirrors ADR-011's local filesystem retention posture while keeping
raw XML and downloaded attachment binaries in separate subtrees.

## Decision

Download annex attachment binaries for rows that have a verified
`source_attachment_url`.

Store downloaded files under:

```text
data/annexes/{law_id}/{mst}/{annex_key}/{source_filename}
```

The leading `./` is a shell/current-directory notation, not stored data.
`stored_file_path` stores the normalized repo-relative path without the
leading dot:

```text
data/annexes/014159/277417/000100E/law0141592025100135805KC_000100E.hwp
```

Add `data/annexes/` to `.gitignore`.

### Download URL resolution

`source_attachment_url` remains unchanged in the database.

For download execution only:

- absolute URLs are used as-is
- relative URLs such as `/LSW/flDownload.do?flSeq=157760669` resolve
  against:

  ```text
  https://www.law.go.kr
  ```

The downloader may append the law.go.kr OC key to the outbound HTTP
request when the source requires it. The OC key is a request credential,
not source provenance.

Hard rule: never persist OC-bearing URLs in `annex_attachments`.

Accepted:

```text
GET https://www.law.go.kr/LSW/flDownload.do?flSeq=157760669&OC=...
```

Stored:

```text
/LSW/flDownload.do?flSeq=157760669
```

If law.go.kr requires a different credential shape, halt and record the
verified request shape before implementation. Do not silently mutate
stored source URLs.

### File write semantics

The downloader must:

1. Query `annex_attachments` joined to `annexes` and `legal_documents`.
2. Select rows where:

   ```sql
   attachment_type IN ('hwp', 'pdf', 'image')
   AND source_attachment_url IS NOT NULL
   AND source_filename IS NOT NULL
   ```

3. Validate `source_filename` as a basename only. Empty names, path
   separators, `.` and `..` halt the download.
4. Create parent directories as needed.
5. Download to a temporary file in the target directory.
6. Compute SHA-256 over the downloaded bytes.
7. Atomically rename the temporary file to the final path.
8. Update the owning `annex_attachments` row:

   ```sql
   stored_file_path = :repo_relative_path,
   checksum_sha256 = :sha256,
   fetched_at = NOW()
   ```

### Idempotency

If an attachment row already has `stored_file_path` and `checksum_sha256`
and the file exists with that checksum, skip it.

If the DB says a file was fetched but the file is missing or the checksum
does not match, halt. Silent re-download would hide local filesystem
corruption or accidental deletion.

If the target file exists but the DB row is not populated, compute its
checksum. If the checksum matches the downloaded bytes, update the row;
otherwise halt and require manual inspection.

### Images

The Phase-1 XML exposes image filenames through `<별표이미지파일명>`, but
does not expose an image download URL. ADR-014 stored those rows with
`source_attachment_url = NULL` deliberately.

Do not construct image URLs from filenames alone.

Execution is staged:

1. Download the HWP/PDF files first because they already have verified
   `source_attachment_url` values.
2. Review the downloaded HWP/PDF files. They may already embed the image
   renderings needed for Phase 1, in which case separate image download is
   not immediately necessary.
3. If separate image binaries are still needed, discover image URLs from a
   verified source such as rendered law.go.kr HTML, a documented API
   response, or another captured upstream URL.
4. Match discovered image URLs to existing image attachment rows by
   `source_filename` basename.
5. Only when there is exactly one verified URL for a filename, update that
   row's `source_attachment_url` without OC parameters, then download the
   file and populate `stored_file_path`, `checksum_sha256`, and
   `fetched_at`.

Zero matches or multiple matches halt. Guessing URL paths from image
filename patterns is rejected.

If a separately verified image URL is not found in the expected law.go.kr
rendered/download path, return to this ADR and re-evaluate the image
retention strategy before implementing another discovery method.

## Options considered

| Option | Verdict |
|--------|---------|
| A. Download HWP/PDF rows with explicit `source_attachment_url`, review the files, then download image rows only after verified image URL discovery | **recommended** — stores real files without inventing image URLs |
| B. Populate `stored_file_path` for every row before download | rejected — records false state |
| C. Infer image URLs from `<별표이미지파일명>` alone | rejected — no verified source URL in the XML |
| D. Store absolute host paths in `stored_file_path` | rejected — not portable across machines or containers |
| E. Store files inside a container-only `/data/annexes` path | rejected — not durable unless separately mounted; repo-local `data/annexes/` matches ADR-011 |
| F. Persist OC-bearing download URLs in `source_attachment_url` | rejected — OC is credential material, not source provenance |

## Consequences

- The 10 Phase-1 HWP/PDF attachment rows become locally durable binary
  files first.
- Downloaded HWP/PDF files are reviewed before deciding whether separate
  image download is necessary.
- The 11 image rows remain source references only until URL provenance is
  verified and matched by filename.
- `stored_file_path` means an actual local file exists and has a recorded
  checksum.
- Downloaded binaries are not committed to git.
- Future extraction/OCR/chunking work can read from `stored_file_path`
  without relying on upstream law.go.kr links.

## Implementation plan after approval

1. Add `data/annexes/` to `.gitignore`.
2. Add a downloader script under `scripts/`.
3. Run it against the Compose `database` service.
4. Download HWP/PDF rows and review the downloaded files for embedded
   image/table renderings.
5. If image files are still needed, add a verified image URL discovery
   pass before downloading image rows.
6. Verify:
   - 10 HWP/PDF rows have `stored_file_path`, `checksum_sha256`,
     `fetched_at`
   - image rows have `stored_file_path IS NULL` unless a verified image
     URL discovery pass populated them
   - files exist under `data/annexes/014159/277417/...`
   - recorded SHA-256 values match the local files
