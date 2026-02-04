# PMOVES.AI Supabase Migrations Guide

**Complete guide for Supabase database migrations in PMOVES.AI**

## Table of Contents

1. [Overview](#overview)
2. [Migration Structure](#migration-structure)
3. [Running Migrations](#running-migrations)
4. [Custom Migrations](#custom-migrations)
5. [Rollback Procedures](#rollback-procedures)
6. [Troubleshooting](#troubleshooting)

---

## Overview

PMOVES.AI uses Supabase's migration system combined with custom PMOVES migrations:

| Source | Purpose | Prefix |
|--------|---------|--------|
| **Supabase (Gotrue)** | Auth, storage, core Supabase features | `20YYYYMMDDhhmmss` |
| **PMOVES** | Custom business logic, geometry bus, models | `YYYY-MM-DD` or `YYYYMMDDhhmmss` |

### Migration Compatibility Notes

**PostgreSQL 17 Compatibility:**
- Use `gen_random_uuid()` instead of `uuid-ossp` extension
- `uuid-ossp` has `pg_read_file` permission restrictions in hardened Postgres
- PostgreSQL 13+ includes `gen_random_uuid()` as built-in

**Ecto/Realtime Compatibility:**
- Realtime (Elixir/Ecto) expects `schema_migrations.version` as `bigint`
- Gotrue creates `schema_migrations` with string versions
- See [Troubleshooting](#troubleshooting) for the fix

---

## Migration Structure

```
pmoves/
├── supabase/
│   ├── migrations/           # SQL migration files
│   │   ├── 2025-09-08_geometry_bus.sql
│   │   ├── 2025-09-08_geometry_bus_rls.sql
│   │   ├── 2025-10-18_geometry_swarm.sql
│   │   ├── 2025-10-18_geometry_swarm_compat.sql
│   │   ├── 2025-10-20_geometry_cgp_views.sql
│   │   ├── 2025-12-08_seed_work_items.sql
│   │   ├── 20250115000000_service_catalog.sql
│   │   ├── 20250115_persona_agent_creation.sql
│   │   ├── 20251230000000_tokenism_simulator.sql
│   │   └── 20260115_model_registry.sql
│   └── initdb/               # Seed data files
│       ├── 02_seed.sql
│       ├── 06_media_analysis.sql
│       ├── 08_geometry_seed.sql
│       ├── 09_geometry_rls.sql
│       ├── 10_archon_prompts_seed.sql
│       └── 12_model_registry_seed.sql
└── db/                      # Additional seed files (v5.x versions)
    ├── v5_12_seed.sql
    ├── v5_12_grounded_personas.sql
    ├── v5_13_geometry_swarm.sql
    ├── v5_13_persona_enhancements.sql
    ├── v5_13_pmoves_core_rest_grants.sql
    └── v5_14_seed_standard_personas.sql
```

---

## Running Migrations

### Initial Bootstrap (All Migrations)

```bash
cd pmoves
make supabase-bootstrap
```

This applies all migrations in:
1. `supabase/migrations/*.sql` (PMOVES custom)

### Individual Migration

```bash
# Apply single migration
docker exec -i pmoves-supabase-db-1 psql -U postgres -d postgres < supabase/migrations/YOUR_FILE.sql
```

### Check Migration Status

```bash
# View applied migrations
docker exec pmoves-supabase-db-1 psql -U postgres -d postgres \
  -c "SELECT * FROM public.schema_migrations ORDER BY version DESC LIMIT 20;"
```

---

## Custom Migrations

### Geometry Bus (CHIT)

**Files:**
- `2025-09-08_geometry_bus.sql` - Core tables (anchors, constellations, shape_points)
- `2025-09-08_geometry_bus_rls.sql` - Row Level Security policies
- `2025-10-20_geometry_cgp_views.sql` - CGP integration views

**Tables Created:**
- `public.anchors` - CHIT encoded data anchors
- `public.constellations` - Anchor groupings
- `public.shape_points` - Multi-modal shape references
- `public.shape_index` - Shape lookup index

### Geometry Swarm

**Files:**
- `2025-10-18_geometry_swarm.sql` - Parameter packs and swarm runs
- `2025-10-18_geometry_swarm_compat.sql` - Compatibility columns

**Tables Created:**
- `public.geometry_parameter_packs` - CGP parameters
- `public.geometry_swarm_runs` - Swarm execution records

### Service Catalog

**File:** `20250115000000_service_catalog.sql`

**Tables Created:**
- `pmoves_core.service_catalog` - PMOVES service registry
- `pmoves_core.v_active_services` - Active services view

**Seeded Data:** 28 PMOVES services with metadata

### Model Registry

**File:** `20260115_model_registry.sql`

**Tables Created:**
- `pmoves_core.model_providers` - LLM provider configurations
- `pmoves_core.models` - Model definitions
- `pmoves_core.model_aliases` - Model name aliases
- `pmoves_core.service_model_mappings` - Service-to-model mappings
- `pmoves_core.model_deployments` - Deployment tracking

### Persona Agents

**File:** `20250115_persona_agent_creation.sql`

**Tables Created:**
- `pmoves_core.personas` - Agent persona definitions
- `pmoves_core.persona_enhancements` - Persona extensions

### Tokenism Simulator

**File:** `20251230000000_tokenism_simulator.sql`

**Tables Created:**
- `pmoves_core.simulations` - Token economy simulations
- `pmoves_core.simulation_weekly_metrics` - Weekly metrics
- `pmoves_core.simulation_calibration` - Calibration data

**Note:** Uses `gen_random_uuid()` instead of `uuid-ossp` for PostgreSQL 17 compatibility.

### Work Items

**File:** `2025-12-08_seed_work_items.sql`

**Tables Created:**
- `public.integration_work_items` - PMOVES integration backlog

**Seeded Data:** 21 initial work items for various PMOVES integrations

---

## Seed Data Files

### Supabase initdb Seeds

Located in `pmoves/supabase/initdb/`:

| File | Purpose | Data Seeded |
|------|---------|-------------|
| `02_seed.sql` | Studio board demo | 1 demo board entry |
| `06_media_analysis.sql` | Media analysis config | Analysis presets |
| `08_geometry_seed.sql` | CHIT geometry demo | Anchors, constellations, points |
| `09_geometry_rls.sql` | Geometry RLS policies | Row-level security |
| `10_archon_prompts_seed.sql` | Archon prompts | Pre-configured agent prompts |
| `12_model_registry_seed.sql` | Model registry | LLM provider configurations |

### db/ Version Seeds

Located in `pmoves/db/` (v5.x versioned seeds):

| File | Purpose | Row Count |
|------|---------|------------|
| `v5_12_seed.sql` | Base seed data | 90 lines |
| `v5_12_grounded_personas.sql` | Grounded personas | 120 lines |
| `v5_13_geometry_swarm.sql` | Geometry swarm configs | 83 lines |
| `v5_13_persona_enhancements.sql` | Persona extensions | 100 lines |
| `v5_13_pmoves_core_rest_grants.sql` | REST API grants | 20 lines |
| `v5_14_seed_standard_personas.sql` | **Standard personas catalog** | 1515 lines |

**v5_14 Standard Personas** (Most Important):
- Seeds 8 production-ready personas for agent orchestration
- Includes: Developer, Researcher, Writer, Analyst, Designer, Manager, Engineer, Scientist
- Each persona has: thread_type, model_preference, temperature, system prompts, tools_access, behavior_weights
- See [Personas section](#standard-personas-catalog) below

---

## Standard Personas Catalog

The `v5_14_seed_standard_personas.sql` seeds 8 production-ready personas:

| Persona | Thread Type | Model | Temperature | Purpose |
|---------|-------------|-------|-------------|---------|
| Developer | chained | claude-sonnet-4-5 | 0.3 | Code, PR reviews, debugging |
| Researcher | parallel | claude-sonnet-4-5 | 0.7 | Research, synthesis |
| Writer | fusion | claude-sonnet-4-5 | 0.8 | Content creation |
| Analyst | big | claude-sonnet-4-5 | 0.2 | Deep analysis |
| Designer | chained | claude-sonnet-4-5 | 0.4 | UX/UI design |
| Manager | fusion | claude-sonnet-4-5 | 0.5 | Coordination |
| Engineer | chained | claude-sonnet-4-5 | 0.3 | Technical design |
| Scientist | parallel | claude-sonnet-4-5 | 0.6 | Experiments |

**Thread Types:**
- `base`: Single conversation, no memory
- `chained`: Sequential reasoning
- `parallel`: Multi-threaded exploration
- `fusion`: Synthesizes multiple outputs
- `big`: Extended context, deep analysis

**Behavior Weights** (decode/retrieve/generate):
- `decode`: Understanding existing context (0.0-1.0)
- `retrieve`: Fetching external knowledge (0.0-1.0)
- `generate`: Creating new content (0.0-1.0)

---

## Rollback Procedures

### Manual Rollback

```bash
# Connect to database
docker exec -it pmoves-supabase-db-1 psql -U postgres -d postgres

# Drop specific table (example)
DROP TABLE IF EXISTS public.new_feature CASCADE;

# Remove migration record
DELETE FROM public.schema_migrations WHERE version = '20240101000000';
```

### Schema Rollback

For major schema changes, create a rollback migration:

```sql
-- migrations/20240101000001_rollback_feature.sql

-- Drop new tables
DROP TABLE IF EXISTS public.new_feature CASCADE;

-- Restore previous schema
ALTER TABLE public.existing_table DROP COLUMN new_column;

-- Remove migration record
DELETE FROM public.schema_migrations WHERE version = '20240101000000';
```

---

## Troubleshooting

### Realtime Migration Error

**Symptom:**
```
** (Postgrex.Error) ERROR 42703 (undefined_column):
column "inserted_at" of relation "schema_migrations" does not exist
```

**Cause:** Gotrue creates `schema_migrations` with incompatible schema for Ecto.

**Fix:** See [Realtime Schema Migrations Error](PRODUCTION_SUPABASE.md#realtime-schema-migrations-error) in the main Supabase guide.

### UUID Extension Error

**Symptom:**
```
ERROR:  permission denied for function pg_read_file
```

**Cause:** `uuid-ossp` extension requires `pg_read_file` which is restricted in hardened Postgres.

**Fix:** Use `gen_random_uuid()` (built-in PostgreSQL 13+) instead:

```sql
-- ❌ WRONG (requires uuid-ossp)
id UUID PRIMARY KEY DEFAULT uuid_generate_v4()

-- ✅ CORRECT (built-in)
id UUID PRIMARY KEY DEFAULT gen_random_uuid()
```

### Role Does Not Exist

**Symptom:**
```
ERROR:  role "anon" does not exist
ERROR:  role "authenticated" does not exist
```

**Cause:** Supabase roles not created during initial setup.

**Fix:**
```sql
DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'anon') THEN
    CREATE ROLE anon NOLOGIN NOINHERIT;
  END IF;
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'authenticated') THEN
    CREATE ROLE authenticated NOLOGIN NOINHERIT;
  END IF;
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'service_role') THEN
    CREATE ROLE service_role NOLOGIN NOINHERIT BYPASSRLS;
  END IF;
END $$;

GRANT USAGE ON SCHEMA public, pmoves_core TO anon, authenticated, service_role;
```

### Schema Already Exists

**Symptom:**
```
ERROR:  schema "auth" already exists
```

**Fix:** Use `IF NOT EXISTS` in migrations:
```sql
CREATE SCHEMA IF NOT EXISTS auth;
CREATE SCHEMA IF NOT EXISTS storage;
```

---

## Best Practices

### Migration Naming

| Pattern | Usage | Example |
|---------|-------|---------|
| `YYYY-MM-DD_description.sql` | PMOVES custom | `2025-09-08_geometry_bus.sql` |
| `YYYYMMDDhhmmss_description.sql` | Supabase-style | `20250115000000_service_catalog.sql` |

### Migration Guidelines

1. **Use IF NOT EXISTS:** For tables, schemas, indexes
2. **Use `gen_random_uuid()`:** Not `uuid_generate_v4()`
3. **Use `timestamp without time zone`:** Not `timestamptz` for schema_migrations
4. **Comment complex logic:** Explain non-obvious SQL
5. **Test locally first:** Apply migrations on dev database before production

### Example Migration Template

```sql
-- PMOVES.AI Migration: Feature Description
-- Date: 2025-01-15
-- Author: Your Name
-- Jira Issue: PMOVES-123

-- Create table
CREATE TABLE IF NOT EXISTS public.new_feature (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  metadata JSONB DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_new_feature_name
  ON public.new_feature(name);

-- Enable RLS
ALTER TABLE public.new_feature ENABLE ROW LEVEL SECURITY;

-- Create policies
DROP POLICY IF EXISTS read_new_feature_all ON public.new_feature;
CREATE POLICY read_new_feature_all ON public.new_feature
  FOR SELECT USING (auth.uid() IS NOT NULL);

-- Add comment
COMMENT ON TABLE public.new_feature IS 'New feature for X';
```

---

## See Also

- **[PRODUCTION_SUPABASE.md](PRODUCTION_SUPABASE.md)** - Complete Supabase guide
- **[PORT_REGISTRY.md](PORT_REGISTRY.md)** - Service port assignments
- **[PRODUCTION_HARDENED.md](PRODUCTION_HARDENED.md)** - Security requirements
