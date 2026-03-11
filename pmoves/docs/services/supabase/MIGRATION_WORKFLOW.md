# Supabase Migration Workflow

**Canonical flow for schema initialization and incremental migration.**

## Two-Phase Initialization

PMOVES uses a dual-path schema strategy:

| Phase | Directory | Trigger | Purpose |
|-------|-----------|---------|---------|
| **1 — initdb** | `supabase/initdb/` (23 files) | Fresh Postgres container start | Full schema bootstrap + seed data |
| **2 — migrations** | `supabase/migrations/` (16 files) | `make supa-migrate` or Supabase CLI | Incremental schema updates on existing DB |

### When Each Phase Runs

- **initdb/**: Executes automatically when `supabase-db` container starts with an empty data volume. Files run in alphanumeric order (`00_` → `17_`). This is the "clean slate" path — development environments use `make volume-reset SERVICE=supabase-db` to trigger re-initialization.

- **migrations/**: Applied via `supabase db push` or `make supa-migrate` against a running database. Used for production upgrades where data must be preserved. Tracked by Supabase's migration history table.

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
| `pmoves/db/` | 6 files | Versioned schema updates (`v5_12_*`, `v5_13_*`, `v5_14_*`) — legacy, being consolidated |
| `pmoves/migrations/` | 3 files | Root-level migrations (large, numbered `001-002`) — legacy |

## Common Operations

```bash
# Fresh database (dev): destroy volume and reinitialize
make -C pmoves volume-reset SERVICE=supabase-db
make -C pmoves up-supabase

# Apply migrations to running database
make -C pmoves supa-migrate

# Check migration status
supabase db status --db-url "postgresql://supabase_admin:${DB_PASSWORD}@localhost:5432/postgres"
```

## Postgres 17 Compatibility

All SQL uses `gen_random_uuid()` (built-in since PG 13) instead of the `uuid-ossp` extension. The `uuid-ossp` extension has `pg_read_file` permission restrictions in hardened Postgres 17.
