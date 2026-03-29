-- Supabase Internal Prerequisites
-- Creates databases and schema ownership needed by Supabase services:
--   analytics/Logflare → _supabase database
--   realtime           → _realtime, realtime schema ownership
--   supavisor/pooler   → _supavisor, supavisor schemas
--
-- Runs BEFORE all other PMOVES initdb scripts (00_pmoves_schema.sql+).
-- Idempotent: safe to run multiple times.

-- 1. _supabase database (required by Logflare/analytics)
SELECT 'CREATE DATABASE _supabase'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '_supabase')\gexec

-- Set _supabase database owner so Logflare can run Ecto migrations
SELECT 'ALTER DATABASE _supabase OWNER TO supabase_admin'
WHERE EXISTS (SELECT FROM pg_roles WHERE rolname = 'supabase_admin')
  AND EXISTS (SELECT FROM pg_database WHERE datname = '_supabase')\gexec

-- 2. Schemas needed by Supabase services (in the current/main database)
CREATE SCHEMA IF NOT EXISTS _realtime;
CREATE SCHEMA IF NOT EXISTS realtime;
CREATE SCHEMA IF NOT EXISTS _supabase;
CREATE SCHEMA IF NOT EXISTS _supavisor;
CREATE SCHEMA IF NOT EXISTS supavisor;

-- NOTE: _analytics schema must be created in the _supabase database, not here.
-- See bootstrap_db.sh Step 3c which runs:
--   CREATE SCHEMA IF NOT EXISTS _analytics in _supabase DB
-- Logflare connects to _supabase DB and runs Ecto migrations there.

-- 3. Schema ownership for Ecto migrations (realtime, pooler)
DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'supabase_admin') THEN
    ALTER SCHEMA _realtime OWNER TO supabase_admin;
    ALTER SCHEMA realtime OWNER TO supabase_admin;
    ALTER SCHEMA _supabase OWNER TO supabase_admin;
    ALTER SCHEMA _supavisor OWNER TO supabase_admin;
    ALTER SCHEMA supavisor OWNER TO supabase_admin;
  END IF;
END $$;
