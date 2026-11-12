# Database Migrate

Apply or preview database migrations for PMOVES Supabase.

> **PMOVES does not track its schema with the Supabase CLI.** SQL is applied by
> `make -C pmoves supabase-bootstrap` and every applied file is recorded in
> `public.pmoves_bootstrap_history`. The CLI's own ledger,
> `supabase_migrations.schema_migrations`, is a different table. On a compose-runtime node
> the CLI view can read clean while the PMOVES ledger does not exist at all. Measured on
> node 5090, 2026-11-06, compose runtime: `public.pmoves_bootstrap_history` was missing and
> all 63 migrations and 29 seeds were pending. Always read the PMOVES ledger.

## Usage

```
/db:migrate [action] [migration_name]
```

## Arguments

- `action`: `status`, `up`, `down`, `create`, `preview` (default: `status`)
- `migration_name`: Name for new migration (required for `create`)

## What This Command Does

Run every command from the repository root. The helper below finds the DB container the
same way the bootstrap target does (`pmoves/scripts/supabase/find_db_container.sh`) and runs
`psql` as `supabase_admin` over TCP inside the container. The password is read from the
container's own environment and is never printed.

```bash
db=$(bash pmoves/scripts/supabase/find_db_container.sh running)
admin_psql() { docker exec -i "$db" sh -c 'PGPASSWORD="$POSTGRES_PASSWORD" psql -w -h 127.0.0.1 -U supabase_admin -d "$POSTGRES_DB" -tA "$@"' _ "$@"; }
```

**The database name comes from the container's environment, not the bootstrap's.** Compose
sets the container's `POSTGRES_DB` from `SUPABASE_DB_NAME`, default `postgres`.
`supabase-bootstrap` takes the name from the invoking shell's `POSTGRES_DB`, default `pmoves`.
The two must name the same database, or `status` reads the wrong one and can report `MISSING`
falsely. On node 5090 both resolve to `pmoves` (2026-11-06). If they differ, replace
`"$POSTGRES_DB"` in the helper with the name bootstrap used.

This repo's PreToolUse damage-control hook treats `psql` against a PMOVES database as direct
DB access and asks for approval (`.claude/hooks/damage-control/patterns.yaml` L686), so every `/db:migrate status` run prompts once per query.

1. **Check Migration Status (`status`):**
   ```bash
   # Does the PMOVES ledger exist?
   admin_psql -c "select coalesce(to_regclass('public.pmoves_bootstrap_history')::text, 'MISSING')"

   # Applied counts by kind
   admin_psql -c "select kind, count(*), max(applied_at) from public.pmoves_bootstrap_history group by kind order by kind"

   # Pending = files on disk that are not in the ledger
   pending() { local kind=$1 dir=$2; LC_ALL=C comm -23 \
     <(for f in "$dir"/*.sql; do echo "${f##*/}"; done | LC_ALL=C sort) \
     <(admin_psql -c "select filename from public.pmoves_bootstrap_history where kind='$kind'" | LC_ALL=C sort); }
   pending migration pmoves/supabase/migrations
   pending seed pmoves/supabase/initdb
   ```
   - **`MISSING` means bootstrap has never run on this node.** Every file is pending. Run `up`
   - `pending` lists every file whenever its query fails, so read the `psql` error it prints.
     `relation ... does not exist` agrees with `MISSING`. An authentication or connection error
     means the helper reached the wrong container or database, and the list means nothing
   - The basename loop avoids `xargs`, which fails with "environment is too large for exec"
     under Git Bash on Windows

2. **Apply Migrations (`up`):**
   ```bash
   # Starts the stack if needed, then applies pending migrations, then seeds
   make -C pmoves supabase-bootstrap
   ```
   - `supabase-bootstrap` is the only sanctioned apply path
   - Files apply in `LC_ALL=C` filename order: `pmoves/supabase/migrations/` first, then
     `pmoves/supabase/initdb/`
   - A file already in the ledger is skipped, so the target is safe to re-run
   - In `supabase-bootstrap`, each file runs with `ON_ERROR_STOP=1`. A failing file is reported as
     `FAILED (skipped)` and is NOT recorded; the run continues. Read the
     `applied= skipped= failed=` summary line and re-run `status` afterwards
   - `supabase-bootstrap-no-start` is currently non-functional: single-`$` expansion of
     `${POSTGRES_DB:-pmoves}` at `pmoves/Makefile` L1305 hands `psql` a bare `-d`. Separate lane
   - `supabase-bootstrap-mark-applied` is currently non-functional for the same reason at
     `pmoves/Makefile` L1347. Separate lane

3. **Rollback Migration (`down`):**
   PMOVES migrations are forward-only. Neither the ledger nor the make targets have a revert.
   - Preferred: add a new forward migration that reverses the change, then run `up`
   - Destructive mistake: restore from backup (`/db:backup`)
   - Deleting a ledger row makes the next `up` re-apply that file. It is a live write, so prove
     it against a scratch DB first, and only for idempotent files

4. **Create New Migration (`create`):**
   ```bash
   # Timestamp prefix keeps LC_ALL=C order equal to apply order
   touch "pmoves/supabase/migrations/$(date -u +%Y%m%d%H%M%S)_<migration_name>.sql"
   ```
   - Write it idempotently (`IF NOT EXISTS`, `CREATE OR REPLACE`): the bootstrap re-runs any
     file not yet in the ledger, including on nodes that already have the object

5. **Preview Changes (`preview`):**
   ```bash
   # The files `up` would apply, in apply order
   pending migration pmoves/supabase/migrations
   pending seed pmoves/supabase/initdb
   ```
   Read each pending file before running `up`.

### Supabase CLI runtime only

These apply only on a node running `SUPABASE_RUNTIME=cli` and only describe the CLI's own
ledger. They do not read or write `public.pmoves_bootstrap_history`.

```bash
supabase migration list --db-url "${SUPABASE_DB_URL}"
supabase db push --db-url "${SUPABASE_DB_URL}"
supabase migration repair --status reverted <version>
supabase db diff --schema pmoves_core

# Rebuild the local CLI database from migrations (destroys local data; CLI dev stack only)
supabase db reset
```

An earlier version of this command also queried
`supabase_migrations.schema_migrations` through a `rest/v1/rpc/execute_sql` RPC. That RPC
is **not provisioned**: no migration or seed under `pmoves/supabase/` defines `execute_sql`.

## Safety Rules

### Pre-Migration Checklist
- [ ] Backup database before destructive migrations
- [ ] Review migration SQL before applying
- [ ] Test on local/staging first
- [ ] Ensure rollback plan exists

### BLOCKED in Production
- `DROP TABLE` without backup verification
- `TRUNCATE` on tables with data
- Schema changes during high traffic

### ALLOWED Operations
- `CREATE TABLE`, `ALTER TABLE ADD COLUMN`
- Index creation (use `CONCURRENTLY`)
- New RLS policies
- New functions/triggers

## PMOVES Schema Structure

### Schemas

| Schema | Purpose |
|--------|---------|
| `public` | Default, Supabase auth |
| `pmoves_core` | Main application tables |
| `archon` | Agent prompts & forms |
| `extensions` | pgvector, pg_graphql |

### Key Migration Patterns

**Add New Table:**
```sql
-- pmoves/supabase/migrations/20250101000000_create_agents.sql
CREATE TABLE pmoves_core.agents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    config JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Enable RLS
ALTER TABLE pmoves_core.agents ENABLE ROW LEVEL SECURITY;

-- Create policy
CREATE POLICY "agents_service_access" ON pmoves_core.agents
    FOR ALL USING (auth.role() = 'service_role');

-- Add to replication (if needed)
ALTER PUBLICATION supabase_realtime ADD TABLE pmoves_core.agents;
```

**Add Column (non-breaking):**
```sql
-- Safe: nullable column with default
ALTER TABLE pmoves_core.content_items
ADD COLUMN metadata JSONB DEFAULT '{}';
```

**Add Index (production-safe):**
```sql
-- Use CONCURRENTLY to avoid locking
CREATE INDEX CONCURRENTLY idx_content_items_status
ON pmoves_core.content_items(status);
```

**Add Vector Column:**
```sql
-- Enable pgvector if not exists
CREATE EXTENSION IF NOT EXISTS vector;

-- Add embedding column
ALTER TABLE pmoves_core.documents
ADD COLUMN embedding vector(384);

-- Add HNSW index for similarity search
CREATE INDEX idx_documents_embedding
ON pmoves_core.documents
USING hnsw (embedding vector_cosine_ops);
```

## Output Format

```markdown
## Migration Status (public.pmoves_bootstrap_history)

**Ledger:** present | MISSING (bootstrap has never run on this node)

### Applied
| Kind | Count | Last Applied |
|------|-------|--------------|
| migration | 63 | 2026-11-06 12:00:00 |
| seed | 29 | 2026-11-06 12:00:05 |

### Pending
| Kind | File |
|------|------|
| migration | 20261107000000_add_metadata_column.sql |
```

## Example

```bash
# Check current status
/db:migrate status

# Preview pending changes
/db:migrate preview

# Apply all pending migrations
/db:migrate up

# Plan a rollback (forward-only: write a reversing migration or restore a backup)
/db:migrate down

# Create new migration
/db:migrate create add_user_preferences
```

## Environment Variables

PMOVES path (`make -C pmoves supabase-bootstrap` and the ledger queries above):
- None required on the host. The DB password comes from the container's environment.
- `POSTGRES_DB` - two different readers. `supabase-bootstrap` reads the host shell's value
  (default `pmoves`); the ledger queries read the container's value (set from
  `SUPABASE_DB_NAME`, default `postgres`). Keep them naming the same database

Supabase CLI runtime only:
- `SUPABASE_DB_URL` - Direct Postgres connection (for Supabase CLI)
- `SUPABASE_PROJECT_ID` - For remote migrations

## Migration File Location

```
pmoves/supabase/
├── migrations/                 # applied first, kind=migration
│   ├── 20250101000000_grounded_personas_kb.sql
│   ├── 20250102000000_geometry_swarm.sql
│   └── ...
├── initdb/                     # applied second, kind=seed
│   ├── 00_0_supabase_internal.sql
│   ├── 00_1_pmoves_kb_schema.sql
│   └── ...
└── config.toml
```

Not `supabase/migrations/` at the repository root.

## Notes

- Use transactions for multi-statement migrations
- Document breaking changes in migration comments
- Full bring-up context, including the ledger check: `pmoves/docs/operations/COMPLETE_BRING_UP_RUNBOOK.md` Phase 3 step 4
- Emergency rollback: Contact DBA or use point-in-time recovery
