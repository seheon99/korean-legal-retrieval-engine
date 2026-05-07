# ADR-011 — Raw 법제처 OpenAPI XML retention as a filesystem store

- **Status**: Accepted
- **Date**: 2026-05-01
- **Context layer**: Statute (성문규범) ingestion pipeline
- **Resolves**: ADR-008 "Trade-offs accepted" §1 (the soft dependency
  on raw API XML being replay-available); ADR-008 "Out of scope" §4
  (whether to formalize raw-API-XML retention as its own ADR);
  ADR-008 revisit trigger §1 (retention explicitly not committed)
- **Depends on / aligned with**: ADR-008 (forward policy
  "promote-when-needed / omit-deliberately / retain raw responses
  as the canonical fallback"); ADR-002 (`mst` is the version-specific
  natural key — the natural filename component); ADR-010 (Phase-1
  schema is frozen, so this ADR cannot add a column to
  `legal_documents`)
- **Out of scope (not decided here)**:
  1. Retention of binary attachments (HWP, PDF, image files) referenced
     by `annexes`/`forms`. Separate question with separate trade-offs
     (file sizes are larger, formats are not text-greppable, source URLs
     may expire). Surface as ADR-012 if/when it becomes load-bearing.
  2. Retention of search-endpoint responses (`lawSearch.do`). The
     retained store is for _full document_ responses
     (`lawService.do`), which carry the un-promoted fields ADR-008
     leans on. Search responses are an index, not the corpus.
  3. The fetch script's own implementation (Thread 2 of the
     2026-05-01 plan). ADR-011 commits to a path/format; the script
     writes to it.
  4. Multi-machine replication / cross-region durability. Phase-1
     runs on a single Fedora server; DR posture is "re-fetch from
     API" plus filesystem-level snapshots. Phase-3 concern.
  5. Whether `data/api-samples/` is renamed/repointed. ADR-011
     defines `data/raw/` as the retention path; the relationship
     to the existing samples directory is a documentation/tooling
     decision, not a retention decision.

## Context

ADR-008 ratified the policy "no JSONB on statute tables; promote when
needed, omit deliberately, retain raw responses as the canonical
fallback." The third clause is a soft dependency: ADR-008's
"Trade-offs accepted" §1 explicitly flags that it presumes raw API
responses remain replay-available, but the project has no formal
retention commitment. ADR-008 also lists "raw-XML retention is
explicitly not committed" as its #1 revisit trigger — meaning if this
ADR rejects retention, ADR-008 is revisited and its fallback Option D
(named-field allowlist JSONB on `legal_documents`) activates.

The decision matters because:

- **It is on the critical path for the next implementation session.**
  Ingestion-pipeline code needs to know where raw responses go before
  any parser logic lands. Deciding mid-implementation forces rework.
- **It locks in (or unlocks) ADR-008.** A "yes, retain durably"
  outcome ratifies ADR-008's forward policy. A "no, do not retain"
  outcome triggers ADR-008's fallback and forces a schema change
  before ADR-010's freeze can be considered fully closed.
- **It is precedent-setting for the other category ERDs.**
  사법판단 / 유권해석 / 학술자료 / 입법개정자료 will each face the
  same retention question. A clean shape here travels.

## Empirical basis (verified 2026-05-01 against existing samples)

Files under `data/api-samples/`:

| File                                           | Size    |
| ---------------------------------------------- | ------- |
| `law-228817-중대재해처벌법.xml` (Act)          | 41.4 KB |
| `law-277417-중대재해처벌법시행령.xml` (Decree) | 94.9 KB |
| `search-중대재해.xml` (search response)        | 2.2 KB  |

Phase-1 corpus per-document size: ~140 KB combined for Act + Decree.

Phase-2 plausible upper bound (full active Korean statute corpus, all
five categories under 성문규범):

- Roughly 5,000 active 법령 entries (Acts + Decrees + Rules)
- Average size ~30 KB/document (most are far smaller than
  중대재해처벌법's 시행령)
- Current-versions-only: ~150 MB
- With historical versions retained (~5× plausible factor): ~750 MB

The Phase-2 upper bound is well below any storage threshold that would
force an object-store decision. Fedora local disk handles it
trivially; backup posture is filesystem snapshot or rsync to NAS.

Important characteristic: the corpus is **regenerable from the API**
(Fedora is IP-whitelisted for `lawService.do`). Disk loss is
recoverable, not catastrophic — this affects the durability discussion
in "Trade-offs accepted" below.

## Decision

**Retain every successful `lawService.do` XML response on the
filesystem under `data/raw/{law_id}/{mst}.xml`. Indefinite retention.
No compression in Phase-1. `data/raw/` is gitignored. Integrity link
to the database row is `legal_documents.content_hash` (already
required by ADR-010).**

Concrete commitments:

1. **Path**: `data/raw/{law_id}/{mst}.xml`. One directory per law
   (groups versions visually for human debugging); one file per
   version (MST is unique per `legal_documents` row by ADR-002).
2. **Format**: plain UTF-8 XML, byte-for-byte identical to the API
   response body. No re-serialization, no whitespace normalization,
   no encoding conversion.
3. **Lifecycle**: indefinite retention. New MST → new file. Old MSTs
   are kept. No rotation. No time-based pruning.
4. **gitignore**: `data/raw/` is added to `.gitignore` (matching the
   existing `data/api-samples/` convention — operational data, not
   source).
5. **Integrity invariant**: `legal_documents.content_hash` is the
   SHA-256 of the corresponding `data/raw/{law_id}/{mst}.xml`
   contents. The ingestion pipeline computes the hash, writes the
   file, and stores the hash atomically (the sequence is fail-fast:
   any step's failure aborts the row). A periodic verification job
   (out of scope for this ADR; tracked under TODO-7 "measure first")
   can re-walk the store to detect drift.
6. **Backup posture**: filesystem-level snapshots / rsync to a
   separate target. Independent of `pg_dump`. Restoration order is
   filesystem-first, then DB (so that `content_hash` verification is
   meaningful after restore).
7. **Write semantics**: ingestion writes are atomic — write to
   `data/raw/{law_id}/{mst}.xml.tmp`, fsync, rename to final name.
   Standard atomic-rename pattern; avoids half-written files on crash.

## Options considered

| Option                                                                            | Verdict                                       |
| --------------------------------------------------------------------------------- | --------------------------------------------- |
| **A. Filesystem `data/raw/{law_id}/{mst}.xml`, indefinite retention, gitignored** | **proposed**                                  |
| B. Database column `legal_documents.raw_xml TEXT` (TOAST-backed)                  | rejected — see "Why A over B"                 |
| C. Object store (S3-compatible: actual S3, MinIO, R2)                             | rejected — see "Why A over C"                 |
| D. No retention (re-fetch on demand)                                              | rejected — triggers ADR-008 fallback Option D |
| E. Filesystem with gzip compression in Phase-1                                    | rejected as primary; held as Phase-2+ revisit |

### Why A over B — the strongest competitor

B ("put raw XML in a TOAST-backed column on `legal_documents`") is the
steelman because it offers a single source of truth: the row and its
raw provenance live and die together, backups are unified under
`pg_dump`, and the integrity invariant is structurally enforced (no
hash check needed — they cannot drift). The arguments **for** B:

1. **Atomicity.** Insert the parsed row and the raw XML in one
   transaction. No "what if the file write succeeded but the row
   insert failed" recovery logic.
2. **Single backup track.** `pg_dump` captures everything. No
   separate filesystem snapshot policy.
3. **No drift surface.** Hash mismatch can't happen because there's
   only one copy.
4. **Operationally portable.** A schema-only deployment (psql + the
   migration file) reproduces the data layer exactly; no
   filesystem-shape dependency.

The arguments **against** B (and why A wins):

1. **`legal_documents` is a hot table.** It is joined to `chunks` on
   every retrieval query. Adding a 30-100 KB TOAST-backed column to
   every row pushes detoasting work onto unrelated query plans even
   when `raw_xml` is not in the SELECT list, because TOAST overhead
   is per-row metadata. The penalty is small per row but persistent.
2. **`pg_dump` size and rebuild time bloat.** A multi-GB statute
   corpus (Phase-2) means multi-GB `pg_dump` output dominated by
   raw XML. Restore time becomes a function of corpus size, not
   schema complexity.
3. **Inspection friction.** ADR drafting routinely greps the API
   samples (this ADR did exactly that to size the corpus). Putting
   raw XML in the DB requires a `psql` + `\copy` round-trip for
   every grep. The friction is real and recurring.
4. **ADR-010 froze the schema.** Adding `raw_xml TEXT` to
   `legal_documents` is a Phase-2 additive migration, not a Phase-1
   change. Choosing B today means either deferring retention until
   `002_*.sql` (and accepting the ADR-008 dependency hangs open) or
   re-opening the freeze. Filesystem retention is orthogonal to
   schema and doesn't pull on the freeze invariant.
5. **The atomicity advantage is over-stated.** A two-write
   sequence with `content_hash` verification and atomic rename
   is well-understood (`tmp + fsync + rename`). The cost of getting
   it right once in the ingestion pipeline is a one-time engineering
   line item; the cost of paying TOAST overhead on every chunks
   query is amortized over the project's lifetime.

A keeps the DB lean, the freeze closed, and inspection cheap, in
exchange for one engineering line of atomic-rename plus one
filesystem-backup track.

### Why A over C — object store

C ("put raw XML in S3 / MinIO / R2") is the architecturally fashionable
answer for binary blobs at scale. The arguments **for** C:

1. **Built for the use case.** Object stores are content-addressable,
   versioned, durable, and replicated by default.
2. **Operationally separated from the application server.** Disk
   pressure on Fedora becomes irrelevant.
3. **Future-proof.** Phase-3 (multi-domain, larger corpus) eventually
   wants this.

The arguments **against** C (and why A wins):

1. **750 MB is not object-store scale.** The Phase-2 upper bound
   does not exceed any reasonable Fedora local-disk allocation.
   Object storage is the right answer for terabyte-scale corpora,
   not for sub-gigabyte legal text.
2. **New infra dependency.** Adding S3 (or MinIO, or R2) introduces
   credentials management, network-error handling, and an
   availability dependency on a service the project does not
   currently use. ADR-011's argument is _for retention as a
   commitment_, not for additional infrastructure.
3. **Premature abstraction.** Per CLAUDE.md §5 ("simpler shipped beats
   elegant unshipped") and the Phase-1 walking-skeleton principle, C
   ships nothing this session. A ships in the same session as the
   fetch script.
4. **Migration to C is straightforward later.** If Phase-3 needs
   object storage, the migration is `data/raw/` → bucket sync, and
   the application reads via an `s3://` URL or similar. Filesystem
   in Phase-1 does not foreclose object store in Phase-3.

### Why A over D — no retention

D ("re-fetch from the API on demand") is the option that triggers
ADR-008's fallback. The arguments **for** D:

1. **Zero storage cost.** Disk usage stays at zero.
2. **Always current.** Re-fetch returns the live response, no drift
   risk.
3. **Re-fetch is feasible.** Fedora is IP-whitelisted; the API
   answers reliably.

The arguments **against** D (and why A wins):

1. **It triggers ADR-008's fallback Option D.** Without retention,
   ADR-008's "promote-when-needed" policy collapses (re-parse needs
   a stable corpus, not a live API). Triggering the fallback means
   reopening ADR-008 and adding a JSONB column to `legal_documents`,
   which is a schema change after ADR-010 freeze. D's "zero cost"
   externalizes its cost onto ADR-008 and ADR-010.
2. **API responses are not deterministic across time.** "Always
   current" is a feature for serving end-users, not for evaluation.
   A retrieval-engine evaluation harness needs to compare today's
   index against a fixed corpus snapshot. D forecloses any
   reproducible evaluation against a historical fixed point.
3. **Re-fetch cost is unbounded under failure.** Network outage,
   API maintenance, IP-whitelist drift — any of which break
   retrieval-pipeline behavior in a way that storing 750 MB of XML
   eliminates. The asymmetric-cost argument from ADR-007 applies
   here too.
4. **It loses ADR-009's parent-lookup robustness.** Title-pattern
   matching for Act-Decree linkage relies on `legal_documents.title`
   being correct — but if that column was misparsed at ingest, the
   raw-XML store is the only place to recover the canonical value.
   D removes that recovery path.

### Why A over E — gzip in Phase-1

E ("filesystem retention but with `.xml.gz` files") halves storage at
the cost of inspection ergonomics.

E's appeal: ~5× XML compression ratio brings the Phase-2 upper bound
from 750 MB to ~150 MB.

Why E loses as primary:

1. **150 MB → 750 MB is not a meaningful difference at Phase-1
   scale.** Both numbers are "negligible on any reasonable disk."
2. **Tooling friction.** Every `grep`, `xmllint`, ADR-drafting
   inspection, or eyeball debug needs `zgrep`/`zcat` instead. The
   project does this routinely (this ADR's empirical basis was a
   direct `ls -la` of plain XML); compression imposes a recurring
   small tax.
3. **Reversibility.** Adding compression later is a one-liner
   (`gzip -r data/raw/`). Removing it later is the same. Not
   path-dependent; defer until storage actually pressures it.

E is held as the Phase-2 revisit if storage growth crosses some
operationally inconvenient threshold (e.g., backup window exceeds
some SLA).

## Trade-offs accepted

- **Two-source layout (filesystem + DB).** Mitigated by
  `legal_documents.content_hash` as the integrity link. The
  ingestion pipeline owns hash computation; periodic verification is
  a future cron-able task.
- **Single-machine durability.** `data/raw/` lives on Fedora local
  disk. Disk failure → restore from filesystem backup, then
  re-fetch any holes from the API. The corpus is
  regenerable-from-source, so this is recovery-bounded, not
  loss-bounded.
- **No history pruning.** Storage grows monotonically. Bounded by
  the API's actual corpus size (small in absolute terms). Revisit
  is mechanical (gzip, or move to object store) if pressure ever
  appears.
- **Adds a "first commitment outside the database" to the project's
  operational surface.** Filesystem-snapshot backup discipline
  becomes a load-bearing assumption. Documented; mitigated by the
  re-fetch fallback.
- **Inspection paths in ADRs and docs use `data/raw/` going
  forward.** `data/api-samples/` remains available for ad-hoc
  `lawSearch.do` samples, but it is not the canonical retention store.
  New tooling and ingestion writes target `data/raw/`.

## Consequences

- `.gitignore` gains `data/raw/`.
- `docs/decisions/ADR-008-jsonb-on-statute-tables.md` "Trade-offs
  accepted" §1 gets a forward-pointer to ADR-011 (the soft
  dependency is now a ratified commitment).
- `docs/decisions/ADR-008-jsonb-on-statute-tables.md` "Out of scope"
  §4 strikes through with a forward-pointer to ADR-011.
- `docs/decisions/ADR-008-jsonb-on-statute-tables.md` "Revisit
  triggers" §1 reframed — retention is now committed, so the
  trigger fires only on _retraction_ of ADR-011, not on its
  absence.
- `CLAUDE.md` §4 mentions retention path and policy in the same
  paragraph that lists ADR-008.
- The fetch script (Thread 2 of today's plan) writes to
  `data/raw/{law_id}/{mst}.xml`, not to `data/api-samples/`.
  `data/api-samples/` keeps existing files but is not the canonical
  store.
- The next-session ingestion pipeline writes to `data/raw/` after a
  successful fetch+parse, computes `content_hash`, and stores it on
  the matching `legal_documents` row.
- No DDL changes (filesystem store; no schema effect). ADR-010
  freeze is not pulled on.

## Verification once accepted

1. `.gitignore` includes `data/raw/`.
2. ADR-008 forward-pointer added to "Trade-offs accepted" §1, "Out
   of scope" §4, and "Revisit triggers" §1.
3. CLAUDE.md §4 updated to reference the retention commitment.
4. `docs/legal-erd-draft.md` has no TODO change (retention is not
   an ERD-side question; it is an ingestion-pipeline policy).
5. ADRs 001–010 invariants unchanged (no schema effect).

## Revisit triggers

ADR-011 is revisited if any of the following hold:

- **Storage pressure crosses an operationally inconvenient
  threshold** (e.g., Fedora disk allocation, backup window SLA).
  Action: switch to E (gzip) first; switch to C (object store) if
  E is insufficient.
- **A second machine enters the operational surface** (e.g.,
  separate ingestion node and serving node). Action: introduce a
  shared store (NFS, object store) so retention is single-sourced
  across machines.
- **Compliance / legal hold requirement appears** (specific
  retention windows, deletion mandates). Action: revisit lifecycle
  clause; add scheduled pruning.
- **The 법제처 API stops being IP-whitelist-stable** (i.e., the
  re-fetch fallback degrades). Action: tighten retention by
  reducing dependency on re-fetch (e.g., add cross-machine
  replication).

## References

- `docs/decisions/ADR-008-jsonb-on-statute-tables.md` — "Trade-offs
  accepted" §1, "Out of scope" §4, "Revisit triggers" §1
- `docs/decisions/ADR-002-identifier-strategy.md` — `mst` as
  version-specific natural key (filename component)
- `docs/decisions/ADR-010-phase-1-ddl-freeze.md` — `content_hash`
  required column on `legal_documents` (integrity invariant link)
- `data/api-samples/law-228817-중대재해처벌법.xml`,
  `law-277417-중대재해처벌법시행령.xml` — existing samples;
  empirical-basis source for size estimates
- `CLAUDE.md` §4 — current-phase ingestion-pipeline / query-layer
  design framing; ADR-011 is one of the three named threads
