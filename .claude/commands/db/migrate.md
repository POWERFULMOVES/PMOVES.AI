# Database Migrate

Apply or preview database migrations for PMOVES Supabase.

## Usage

```
/db:migrate [action] [migration_name]
```

## Arguments

- `action`: `status`, `up`, `down`, `create`, `preview` (default: `status`)
- `migration_name`: Name for new migration (required for `create`)

## What This Command Does

1. **Check Migration Status:**
   ```bash
   # List applied migrations
   supabase migration list --db-url "${SUPABASE_DB_URL}"

   # Or via direct query
   curl -X POST "${SUPABASE_URL}/rest/v1/rpc/execute_sql" \
     -H "apikey: ${SUPABASE_SERVICE_KEY}" \
     -d '{"query": "SELECT * FROM supabase_migrations.schema_migrations ORDER BY version DESC LIMIT 20"}'
   ```

2. **Apply Migrations (up):**
   ```bash
   # Apply pending migrations
   supabase db push --db-url "${SUPABASE_DB_URL}"
   ```

3. **Rollback Migration (down):**
   ```bash
   # Rollback last migration
   supabase migration repair --status reverted <version>
   ```

4. **Create New Migration:**
   ```bash
   supabase migration new <migration_name>
   # Creates: supabase/migrations/<timestamp>_<migration_name>.sql
   ```

5. **Preview Changes:**
   ```bash
   # Show what would be applied
   supabase db diff --schema pmoves_core
   ```

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
-- supabase/migrations/20250101000000_create_agents.sql
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
## Migration Status

### Applied Migrations
| Version | Name | Applied At |
|---------|------|------------|
| 20250601120000 | create_agents | 2025-06-01 12:00:00 |
| 20250601110000 | add_embeddings | 2025-06-01 11:00:00 |

### Pending Migrations
| Version | Name |
|---------|------|
| 20250602090000 | add_metadata_column |

### Last Migration Details
- **Version:** 20250601120000
- **Name:** create_agents
- **Status:** Applied
- **Duration:** 1.2s
```

## Example

```bash
# Check current status
/db:migrate status

# Preview pending changes
/db:migrate preview

# Apply all pending migrations
/db:migrate up

# Rollback last migration
/db:migrate down

# Create new migration
/db:migrate create add_user_preferences
```

## Environment Variables

Required:
- `SUPABASE_URL` - Supabase project URL
- `SUPABASE_SERVICE_KEY` - Service role key
- `SUPABASE_DB_URL` - Direct Postgres connection (for Supabase CLI)

Optional:
- `SUPABASE_PROJECT_ID` - For remote migrations

## Migration File Location

```
supabase/
├── migrations/
│   ├── 20250101000000_initial_schema.sql
│   ├── 20250102000000_add_content_items.sql
│   └── 20250103000000_add_embeddings.sql
├── seed.sql
└── config.toml
```

## Notes

- Always test migrations locally first: `supabase db reset`
- Use transactions for multi-statement migrations
- Document breaking changes in migration comments
- For schema diffs: `supabase db diff --schema pmoves_core`
- Emergency rollback: Contact DBA or use point-in-time recovery
