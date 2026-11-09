# Supabase Migration Workflow

**Canonical flow for schema initialization and incremental migration.**

## Two-Phase Initialization

PMOVES uses a dual-path schema strategy:

| Phase | Directory | Trigger | Purpose |
|-------|-----------|---------|---------|
| **1 — initdb** | `supabase/initdb/` (29 files) | `make -C pmoves supabase-bootstrap` (**not** container start — see below) | Full schema bootstrap + seed data |
| **2 — migrations** | `supabase/migrations/` (59 files) | `make supa-migrate` or Supabase CLI | Incremental schema updates on existing DB |

### When Each Phase Runs

- **initdb/**: Applied by `make -C pmoves supabase-bootstrap` as tracked seeds, in alphanumeric order (`00_` → `18_`).

  **These files do NOT execute at container start**, despite the directory name. `docker-compose.yml:580` mounts them at `./supabase/initdb:/docker-entrypoint-initdb.d/pmoves-init` — a *subdirectory*. The Postgres entrypoint iterates `/docker-entrypoint-initdb.d/*` and only executes entries matching `*.sql`, `*.sql.gz` or `*.sh`; a directory matches none of those. Verified against `supabase/postgres:17.6.1.108` on an empty volume, which logs:

  ```
  /usr/local/bin/docker-entrypoint.sh: ignoring /docker-entrypoint-initdb.d/pmoves-init
  ```

  So a fresh container comes up healthy with an **empty** database and stays that way until `supabase-bootstrap` is run. `make volume-reset SERVICE=supabase-db` clears the volume; it does not re-seed on its own.

  This matters for anything written as a seed: it runs as `supabase_admin` (the role `supabase-bootstrap` connects with), never in the entrypoint's bootstrap context.

- **migrations/**: Applied via `supabase db push` or `make supa-migrate` against a running database. Used for production upgrades where data must be preserved. Tracked by Supabase's migration history table.

For a full PMOVES bootstrap on an existing database, the canonical entrypoint is `make -C pmoves supabase-bootstrap`, which applies `supabase/migrations/*.sql` first and then replays `supabase/initdb/*.sql` as tracked seeds via `public.pmoves_bootstrap_history`.

## The bootstrap ledger records EXIT CODE, not outcome

`supabase-bootstrap` tracks what it has applied in `public.pmoves_bootstrap_history`
(`kind`, `filename`, `applied_at`; PK on `kind, filename`). The apply loop is:

```sh
if admin_psql < "$f" >/tmp/sb_apply.log 2>&1; then
    admin_psql -c "INSERT INTO public.pmoves_bootstrap_history(kind, filename) ..."
else
    fail++; echo "   FAILED (skipped): $name ..."
fi
```

**A file is recorded as applied when `psql` exits 0** — not when it achieved anything.
For unconditional SQL those are the same statement. For a file that guards itself and
returns early they are not: a `DO $$ ... RETURN; ... $$` exits 0, is recorded, and is
skipped by filename on every subsequent run.

The table can express *applied* and *not applied*. A conditional file needs a third
state — *not applicable here* — and there is nowhere to put it.

### The failure this actually caused

`20260818000000_juicefs_meta_scoped_role.sql` created a scoped `juicefs_meta` role and
guarded on the schema existing. But the schema is created by a **seed**
(`initdb/00_2_juicefs_meta_schema.sql`), and migrations run **before** seeds — so on a
fresh database the guard always fired. Reproduced on `supabase/postgres:17.6.1.108`:

```
fresh DB:            role=ABSENT   schema=ABSENT
bootstrap run 1:     migration: applied=1   seed: applied=1
                ->   role=ABSENT   schema=PRESENT      <- migration "applied", created nothing
bootstrap run 2:     migration: skipped=1   seed: skipped=1
                ->   role=ABSENT   schema=PRESENT      <- skipped by ledger, forever
```

It worked on databases bootstrapped *before* the migration landed, because the schema
already existed. So it passed where it was developed and was silently absent on any node
rebuilt from scratch — the worst shape available for a security control, since it
validates in testing and is missing during a rebuild.

### Rule

**If SQL cannot run unconditionally, it does not belong in `supabase/migrations/`.**

Put it in `supabase/initdb/` with a filename that sorts after its dependencies. Seeds run
after migrations, so a seed can depend on schema a migration or an earlier seed created,
and the ledger entry is honest because the file really did do its work. This is the same
rationale recorded in `00_1_pmoves_kb_schema.sql` and `00_2_juicefs_meta_schema.sql`:
a dedicated new seed filename applies on both fresh and already-bootstrapped databases.

If a genuinely node-conditional migration is ever needed, the ledger needs a third state
first — do not encode "not applicable" as a clean return.

## File Naming Conventions

### initdb/ — Numbered ordering
```
00_pmoves_schema.sql      ← Foundation: extensions, schemas, core tables
01_public_init.sql        ← Public schema roles/grants
02_seed.sql               ← Initial seed data
...
17_persona_seed.sql       ← Final seed (59K lines of persona records)
```

Duplicate prefixes (e.g., `06_media_analysis.sql` and `06_upload_events.sql`) are allowed — alphanumeric sort determines order within the same prefix.

### migrations/ — Timestamped (three formats in use)
```
20250115000000_service_catalog.sql      ← YYYYMMDDhhmmss (Supabase CLI standard)
20250115_persona_agent_creation.sql     ← YYYYMMDD (short form)
2025-09-08_geometry_bus.sql             ← YYYY-MM-DD (early convention)
```

**New migrations should use** `YYYYMMDDhhmmss_description.sql` (Supabase CLI default).

## Known Overlaps

The following tables appear in **both** initdb and migrations, guarded by `CREATE TABLE IF NOT EXISTS`:

| Table | initdb File | Migration File |
|-------|-------------|----------------|
| `public.anchors` | `07_geometry_bus.sql` | `2025-09-08_geometry_bus.sql` |
| `public.constellations` | `07_geometry_bus.sql` | `2025-09-08_geometry_bus.sql` |
| `public.shape_points` | `07_geometry_bus.sql` | `2025-09-08_geometry_bus.sql` |
| `public.shape_index` | `07_geometry_bus.sql` | `2025-09-08_geometry_bus.sql` |

**Why this is safe:** Both files use `IF NOT EXISTS` guards. Fresh databases create tables via initdb; existing databases encounter them via migrations (no-op). The duplication exists because the Geometry Bus was added to both paths simultaneously.

**Future cleanup:** Consolidate DDL into initdb only; migration becomes ALTER-only for schema changes.

## Schemas

| Schema | Created By | Purpose |
|--------|-----------|---------|
| `pmoves_core` | `00_pmoves_schema.sql` | Main application schema (agents, sessions, memory) |
| `public` | Postgres default | Geometry Bus, work items, general tables |
| `realtime` | `08_realtime_schema.sql` | Supabase Realtime subscriptions |
| `auth` | Supabase GoTrue | Authentication (managed by GoTrue service) |
| `storage` | Supabase Storage | File storage metadata (managed by Storage service) |

## Additional SQL Directories

| Directory | Files | Purpose |
|-----------|-------|---------|
| `pmoves/db/` | 6 files | Legacy source SQL (`v5_12_*`, `v5_13_*`, `v5_14_*`) referenced by newer seeds; not executed by `supabase-bootstrap` |
| `pmoves/migrations/` | 3 files | Root-level legacy migrations (large, numbered `001-002`); not part of the current Supabase bootstrap path |

## Common Operations

```bash
# Fresh or existing database: apply canonical PMOVES bootstrap
make -C pmoves supabase-bootstrap

# Apply migrations to running database
make -C pmoves supa-migrate

# Check migration status
supabase db status --db-url "postgresql://supabase_admin:${DB_PASSWORD}@localhost:5432/postgres"
```

Do not replay `supabase/initdb/*.sql` seed files directly against an empty database unless you have already applied the dependent migrations they assume.

## Postgres 17 Compatibility

All SQL uses `gen_random_uuid()` (built-in since PG 13) instead of the `uuid-ossp` extension. The `uuid-ossp` extension has `pg_read_file` permission restrictions in hardened Postgres 17.
