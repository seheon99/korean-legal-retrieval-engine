# ADR-015 — Migration management for post-freeze schema changes

- **Status**: Accepted
- **Date**: 2026-05-05
- **Context layer**: Database schema migration workflow
- **Resolves**:
  - How schema changes after the ADR-010 Phase-1 DDL freeze are shipped.
  - The precedent for the first post-freeze migration (`002_*`).
  - How clean Docker dev databases and already-initialized dev databases
    receive the same schema state.
- **Depends on / aligned with**:
  - **ADR-010 (Accepted)** — `001_statute_tables.sql` is the frozen
    Phase-1 baseline; all later schema changes are explicit migrations.
  - **ADR-013 (Accepted)** — `is_current` is semantically superseded by
    `is_head`, but the rename migration is not additive.
  - **ADR-014 (Accepted)** — `annex_attachments` and
    `form_attachments` require the first additive post-freeze migration.
- **Out of scope (not decided here)**:
  1. Production deployment orchestration.
  2. Blue/green or zero-downtime migration policy.
  3. Down migrations for destructive rollback.
  4. Long-term data backfill framework for amendments and chunks.

## Context

The project currently has one schema file:

```text
migrations/001_statute_tables.sql
```

Docker Compose bind-mounts `migrations/` into
`/docker-entrypoint-initdb.d`, so PostgreSQL executes SQL files on the
first boot of an empty data volume. That is sufficient for a clean dev
database, but it does not update an already-initialized database volume.

ADR-014 now needs the first post-freeze migration. This is the point where
the migration mechanism becomes precedent. Choosing it implicitly by
dropping a `002_*.sql` file would be a process decision without review.

The schema is hand-written PostgreSQL DDL. There is no SQLAlchemy model
metadata, no ORM layer, and no need for autogeneration. The DDL itself is
the source artifact.

## Decision

Use **plain, ordered PostgreSQL SQL migration files** under
`migrations/`, backed by an explicit `schema_migrations` ledger table.

Migration file naming:

```text
migrations/001_statute_tables.sql
migrations/002_<slug>.sql
migrations/003_<slug>.sql
```

Rules:

1. Migration numbers are monotonic, three-digit, and never reused.
2. Each file is forward-only. Rollback is a new forward migration unless
   Seheon explicitly asks for a local destructive reset.
3. Files are written as explicit PostgreSQL DDL/DML, not generated from
   model metadata.
4. Migrations run in lexical order.
5. Applied migrations are recorded in:

   ```sql
   CREATE TABLE schema_migrations (
     version     TEXT PRIMARY KEY,
     filename    TEXT NOT NULL,
     applied_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
   );
   ```

6. `001_statute_tables.sql` remains the baseline and is not rewritten.
   The first post-freeze migration bootstraps the ledger by recording
   `001` as already applied when the baseline tables exist.
7. Clean Docker dev volumes may still initialize by executing the ordered
   SQL files through `/docker-entrypoint-initdb.d`.
8. Existing dev databases are upgraded by applying unapplied migrations
   with `psql` or a thin project script that uses the same ordered SQL
   files and ledger table.

## First migration under this ADR

The first migration should be:

```text
migrations/002_annex_form_attachments.sql
```

It should be additive:

- create `schema_migrations` if it does not exist
- record baseline `001_statute_tables.sql`
- create `annex_attachments`
- create `form_attachments`
- add owner/type indexes and attachment-type CHECK constraints
- record `002_annex_form_attachments.sql`

It should **not** drop the pre-ADR-014 attachment columns from `annexes`
or `forms` in the same migration. Those columns are deprecated by
ADR-014, and new ingestion code should stop writing them, but physical
removal is a separate cleanup migration because the requested first
migration is additive.

It should also **not** bundle the ADR-013 `is_current` -> `is_head` rename.
That rename is accepted and still required, but it is not additive and
should ship as its own migration after this precedent is approved.

## Options considered

| Option | Verdict |
|--------|---------|
| A. Ordered raw SQL migrations with `schema_migrations` ledger | **recommended** — matches the current hand-written DDL and keeps schema review direct |
| B. Docker `initdb.d` only, no ledger | rejected — works only for empty dev volumes and gives no applied-state record |
| C. One cumulative schema file rewritten in place | rejected — violates ADR-010's freeze and destroys migration history |
| D. Fully idempotent `CREATE IF NOT EXISTS` files without a ledger | rejected — hides drift and makes partial application harder to detect |

## Consequences

- The migration history stays close to the DDL that reviewers actually
  need to inspect.
- The first additive migration can be applied to the existing Docker
  database without `docker compose down -v`.
- Clean Docker databases still converge by executing the same SQL files in
  order.
- There is no automatic downgrade path. That is acceptable for Phase 1:
  rollback is either a new forward migration or an explicit local volume
  reset.
- The accepted ADR-013 rename remains pending as a separate, non-additive
  migration.

## Approval checkpoint

If accepted, flip status to `Accepted`, then implement
`migrations/002_annex_form_attachments.sql` and the ADR-014 parser/populator
changes.
