# Submodule Migrations Guide

**Status:** Analysis complete - Migration sequencing issues identified
**Date:** 2026-02-04

## Overview

PMOVES.AI has multiple submodules with their own database migrations. This document catalogs all submodule migrations and identifies sequencing issues that need to be resolved.

## Migration Summary by Submodule

| Submodule | Migrations | Status | Issues |
|-----------|------------|--------|---------|
| PMOVES-transcribe-and-fetch | 10 files | ⚠️ Out of sequence | init_db.sql missing V6-V8 |
| PMOVES-DoX | 3 files | ⚠️ Mixed locations | Two migration folders, duplicate tables |
| PMOVES-ToKenism-Multi | 4 files | ⚠️ Path issues | Nested incorrect paths |
| PMOVES-BoTZ | 0 files | ℹ️ None | No SQL migrations (Alembic Python only) |
| PMOVES-Crush | 4 files | ✅ OK | PostgreSQL migrations, self-contained |
| PMOVES-Archon | 1 file | ✅ OK | Single migration tracking table |

---

## 1. PMOVES-transcribe-and-fetch

**Location:** `/PMOVES-transcribe-and-fetch/migrations/`

### Migration Files

| File | Description | Dependencies |
|------|-------------|---------------|
| `supabase_tables_setup.sql` | Base schema: webpage_content, text_content, media_content | None |
| `init_db.sql` | Combined V1-V5 (outdated) | `supabase_tables_setup.sql` |
| `V1_add_webpage_embeddings_and_search.sql` | Add embeddings, update search functions | `webpage_content` table |
| `V2_create_fetch_history_table.sql` | Create fetch_history table | None |
| `V3_add_content_summary_to_fetch_history.sql` | Add content_summary column | V2 |
| `V4_add_raw_content_path_to_fetch_history.sql` | Add raw_content_path column | V2 |
| `V5_add_supabase_content_id_to_fetch_history.sql` | Add supabase_content_id column | V2 |
| `V6_add_models_configs_agents_tables.sql` | Create llm_models, app_configurations, agent_registry | None |
| `V7_create_crawl_presets_table.sql` | Create crawl_presets table with RLS | None |
| `V8_add_supabase_storage_path_to_fetch_history.sql` | Add supabase_storage_path column | V2 |

### Issues Identified

1. **Out of Sequence:** `init_db.sql` only includes V1-V5 (created before V6-V8 existed)
2. **Missing V6-V8:** The combined `init_db.sql` needs to be updated to include V6-V8
3. **PostgreSQL 17 Compatibility:** Uses `uuid-ossp` extension instead of built-in `gen_random_uuid()`
4. **Dependency Confusion:** V1 migrations run AFTER base schema but naming suggests they should run first

### Recommended Execution Order

```bash
# 1. Base tables (REQUIRED FIRST)
psql -f supabase_tables_setup.sql

# 2. Combined migrations (includes V1-V5)
psql -f init_db.sql

# 3. Run V6-V8 individually
psql -f V6_add_models_configs_agents_tables.sql
psql -f V7_create_crawl_presets_table.sql
psql -f V8_add_supabase_storage_path_to_fetch_history.sql
```

### Fix Required

Update `init_db.sql` to include V6-V8 at the end of the file.

---

## 2. PMOVES-DoX

**Location:** `/PMOVES-DoX/backend/migrations/`

### Migration Files

| File | Description | Issues |
|------|-------------|---------|
| `001_cipher_schema.sql` | Cipher memory, user_prefs, skills_registry | Uses `uuid-ossp` |
| `supabase/001_init.sql` | Artifacts, documents, search chunks (different schema) | Duplicate `crawl_presets` |
| `002_cipher_user_scoping.sql` | Add user_id to cipher_memory, update RLS | None |

### Issues Identified

1. **Two Migration Folders:** Migrations split between root and `supabase/` subfolder
2. **Duplicate Tables:** `crawl_presets` exists in both `schema.sql` and transcribe-fetch V7
3. **PostgreSQL 17 Compatibility:** Uses `uuid-ossp` extension instead of `gen_random_uuid()`

### Schema Conflict

The `crawl_presets` table is defined in TWO places:
- `/PMOVES-DoX/backend/app/db/schema.sql` (lines 162-174)
- `/PMOVES-transcribe-and-fetch/migrations/V7_create_crawl_presets_table.sql`

These should be consolidated into a single source of truth.

### Recommended Execution Order

```bash
# For Cipher features (DoX internal)
psql -f backend/migrations/001_cipher_schema.sql
psql -f backend/migrations/002_cipher_user_scoping.sql

# For Supabase integration
psql -f backend/migrations/supabase/001_init.sql
```

---

## 3. PMOVES-ToKenism-Multi

**Location:** `/PMOVES-ToKenism-Multi/`

### Migration Files

| File | Description | Issues |
|------|-------------|---------|
| `integrations/PMOVES-DoX/backend/migrations/001_cipher_schema.sql` | Copy of DoX migrations | Duplicate |
| `integrations/PMOVES-DoX/backend/migrations/supabase/001_init.sql` | Copy of DoX migrations | Duplicate |
| `home/pmoves/PMOVES.AI/integrations-workspace/PMOVES-DoX/backend/migrations/*` | Wrong nested path | Path error |

### Issues Identified

1. **Nested Path Problem:** Files at `/PMOVES-ToKenism-Multi/home/pmoves/PMOVES.AI/...` indicate incorrect submodule nesting
2. **Duplicate Migrations:** Contains copies of DoX migrations instead of its own
3. **No Native Migrations:** This submodule appears to use parent's migrations rather than its own

### Recommended Action

The nested paths suggest the submodule needs to be re-initialized. Clean up and re-submodule:

```bash
# Remove and re-add submodule properly
git submodule deinit -f PMOVES-ToKenism-Multi
git rm -f PMOVES-ToKenism-Multi
git submodule add <correct-url> PMOVES-ToKenism-Multi
```

---

## 4. PMOVES-BoTZ

**Location:** `/PMOVES-BoTZ/`

### Migration Files

**None found** - This submodule uses Alembic (Python) for migrations, not SQL.

### Status

Alembak migrations would be in:
- `alembic/versions/` directory
- Run via `alembic upgrade head` command

---

## 5. PMOVES-Crush

**Location:** `/PMOVES-crush/internal/db/migrations/`

### Migration Files

| File | Description |
|------|-------------|
| `20250424200609_initial.sql` | Initial schema |
| `20250515105448_add_summary_message_id.sql` | Add summary_message_id |
| `20250624000000_add_created_at_indexes.sql` | Add indexes |
| `20250627000000_add_provider_to_messages.sql` | Add provider column |

### Status

✅ **Self-contained** - These migrations follow timestamp-based naming and are independent of other submodules.

---

## 6. PMOVES-Archon

**Location:** `/PMOVES-Archon/migration/0.1.0/`

### Migration Files

| File | Description |
|------|-------------|
| `008_add_migration_tracking.sql` | Migration tracking table |

### Status

✅ **Single migration** - Just adds migration tracking. Main schema is created by application on startup.

---

## PostgreSQL 17 Compatibility Issues

All submodules using `uuid-ossp` extension should be updated:

### Current (Incompatible with hardened Postgres)

```sql
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
-- Uses uuid_generate_v4()
```

### Target (PostgreSQL 13+ compatible)

```sql
-- No extension needed - gen_random_uuid() is built-in
-- Uses gen_random_uuid()
```

### Files Requiring Updates

1. `/PMOVES-transcribe-and-fetch/migrations/V1_add_webpage_embeddings_and_search.sql` (line 7)
2. `/PMOVES-transcribe-and-fetch/migrations/init_db.sql` (line 7)
3. `/PMOVES-DoX/backend/migrations/supabase/001_init.sql` (line 1)
4. Any other files using `uuid_generate_v4()`

---

## Consolidation Plan

### Step 1: Update init_db.sql in transcribe-and-fetch

Add V6-V8 to the combined migration file:

```sql
-- At the end of init_db.sql, add:

-- V6: Create llm_models, app_configurations, agent_registry tables
-- (content from V6_add_models_configs_agents_tables.sql)

-- V7: Create crawl_presets table with RLS
-- (content from V7_create_crawl_presets_table.sql)

-- V8: Add supabase_storage_path to fetch_history
-- (content from V8_add_supabase_storage_path_to_fetch_history.sql)
```

### Step 2: Fix PostgreSQL 17 compatibility

Global find-and-replace across all submodule migrations:

```bash
# Find all occurrences
grep -r "uuid-ossp" /PMOVES-*/migrations/
grep -r "uuid_generate_v4()" /PMOVES-*/migrations/

# Replace with gen_random_uuid()
```

### Step 3: Resolve DoX schema conflicts

Consolidate `crawl_presets` table into a single migration:
- Keep in `PMOVES-transcribe-and-fetch/migrations/V7_create_crawl_presets_table.sql`
- Remove from `PMOVES-DoX/backend/app/db/schema.sql` (duplicate)

### Step 4: Fix Tokenism submodule paths

Re-initialize the submodule with correct paths.

---

## Testing Migration Order

To verify migrations run correctly:

```bash
# Create test database
createdb pmoves_test

# Run base schema
psql -d pmoves_test -f /PMOVES-transcribe-and-fetch/supabase_tables_setup.sql

# Run combined migrations
psql -d pmoves_test -f /PMOVES-transcribe-and-fetch/migrations/init_db.sql

# Run remaining migrations
for v in V6 V7 V8; do
  psql -d pmoves_test -f /PMOVES-transcribe-and-fetch/migrations/${v}_*.sql
done

# Verify all tables exist
psql -d pmoves_test -c "\dt" | grep -E "(webpage|fetch|llm|crawl)"
```

---

## Migration Status Dashboard

| Submodule | Migrations | Sequencing | PG17 Compatible | RLS Enabled |
|-----------|------------|------------|-----------------|-------------|
| transcribe-and-fetch | V1-V8 | ⚠️ Fix needed | ⚠️ Needs update | Partial |
| DoX | 001-002 | ⚠️ Fix needed | ⚠️ Needs update | Yes |
| Tokenism | Duplicates | ❌ Path error | ⚠️ Needs update | Yes |
| BoTZ | Alembic | N/A | N/A | N/A |
| Crush | 4 files | ✅ OK | ✅ OK | Yes |
| Archon | 1 file | ✅ OK | ✅ OK | N/A |

---

## Next Steps

1. **Fix init_db.sql** - Add V6-V8 to combined migration
2. **Update UUID generation** - Replace `uuid-ossp` with `gen_random_uuid()`
3. **Resolve duplicate tables** - Consolidate `crawl_presets` definition
4. **Fix Tokenism paths** - Re-initialize submodule correctly
5. **Create migration runner** - Script to run all submodule migrations in correct order

---

## Related Documentation

- [SUPABASE_MIGRATIONS.md](./SUPABASE_MIGRATIONS.md) - Main PMOVES Supabase migrations
- [NEO4J_MIGRATIONS.md](./NEO4J_MIGRATIONS.md) - Neo4j CHIT mind map migrations
- [PRODUCTION_SUPABASE.md](./PRODUCTION_SUPABASE.md) - Supabase setup guide
