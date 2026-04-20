create extension if not exists "uuid-ossp";
create extension if not exists "pgcrypto";
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_catalog.pg_available_extensions WHERE name = 'vector') THEN
    EXECUTE 'CREATE EXTENSION IF NOT EXISTS "vector"';
  ELSE
    RAISE NOTICE 'pgvector extension not available; skipping CREATE EXTENSION vector';
  END IF;
END $$;

create schema if not exists auth;
create schema if not exists storage;
create schema if not exists realtime;

alter table if exists schema_migrations
  add column if not exists inserted_at timestamp without time zone default timezone('utc', now());

alter table if exists schema_migrations
  alter column version type bigint using version::bigint;

alter table if exists schema_migrations
  alter column inserted_at type timestamp without time zone using timezone('utc', inserted_at),
  alter column inserted_at set default timezone('utc', now());

create schema if not exists pmoves_core;

create table if not exists pmoves_core.agent (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  role text,
  meta jsonb default '{}'::jsonb,
  created_at timestamptz default now()
);

create table if not exists pmoves_core.session (
  id uuid primary key default gen_random_uuid(),
  agent_id uuid references pmoves_core.agent(id) on delete cascade,
  user_id text,
  meta jsonb default '{}'::jsonb,
  created_at timestamptz default now()
);

create table if not exists pmoves_core.message (
  id uuid primary key default gen_random_uuid(),
  session_id uuid references pmoves_core.session(id) on delete cascade,
  role text check (role in ('user','assistant','system','tool')),
  content text,
  tokens int,
  meta jsonb default '{}'::jsonb,
  created_at timestamptz default now()
);

DO $$
DECLARE
  has_vector boolean := EXISTS (
    SELECT 1 FROM pg_type WHERE typname = 'vector'
  );
BEGIN
  IF has_vector THEN
    EXECUTE $SQL$
      create table if not exists pmoves_core.memory (
        id uuid primary key default gen_random_uuid(),
        agent_id uuid references pmoves_core.agent(id) on delete cascade,
        kind text not null,
        key text not null,
        value jsonb not null,
        embedding vector(1536),
        created_at timestamptz default now()
      )
    $SQL$;

    -- Upgrade legacy float4[] columns to vector when the extension becomes available.
    IF EXISTS (
      SELECT 1
      FROM information_schema.columns
      WHERE table_schema = 'pmoves_core'
        AND table_name = 'memory'
        AND column_name = 'embedding'
        AND udt_name = '_float4'
    ) THEN
      BEGIN
        EXECUTE 'ALTER TABLE pmoves_core.memory ALTER COLUMN embedding TYPE vector(1536) USING embedding::vector(1536)';
      EXCEPTION
        WHEN OTHERS THEN
          RAISE NOTICE 'Could not convert pmoves_core.memory.embedding to vector(1536): %', SQLERRM;
      END;
    END IF;

    -- Attempt ivfflat; fall back to hnsw if unsupported
    BEGIN
      EXECUTE 'create index if not exists memory_embedding_idx on pmoves_core.memory using ivfflat (embedding vector_cosine_ops)';
    EXCEPTION
      WHEN OTHERS THEN
        BEGIN
          EXECUTE 'create index if not exists memory_embedding_idx on pmoves_core.memory using hnsw (embedding vector_cosine_ops)';
        EXCEPTION
          WHEN OTHERS THEN
            RAISE NOTICE 'Skipping vector index on pmoves_core.memory.embedding: %', SQLERRM;
        END;
    END;
  ELSE
    EXECUTE $SQL$
      create table if not exists pmoves_core.memory (
        id uuid primary key default gen_random_uuid(),
        agent_id uuid references pmoves_core.agent(id) on delete cascade,
        kind text not null,
        key text not null,
        value jsonb not null,
        embedding float4[],
        created_at timestamptz default now()
      )
    $SQL$;

    RAISE NOTICE 'pgvector extension not available; skipping vector index on pmoves_core.memory.embedding';
  END IF;
END $$;

create index if not exists memory_agent_kind_key_idx on pmoves_core.memory(agent_id, kind, key);

create table if not exists pmoves_core.event_log (
  id bigserial primary key,
  occurred_at timestamptz default now(),
  session_id uuid,
  agent_id uuid,
  event_type text not null,
  payload jsonb not null

-- =============================================================================
-- Row Level Security for pmoves_core schema (C-02)
-- Deny anon access to all core tables; service_role has full access.
-- =============================================================================

-- Revoke all from anon on the entire schema
DO $$ BEGIN
  EXECUTE 'REVOKE ALL ON ALL TABLES IN SCHEMA pmoves_core FROM anon';
EXCEPTION WHEN OTHERS THEN
  RAISE NOTICE 'REVOKE from anon on pmoves_core: %', SQLERRM;
END $$;

-- Grant full access to service_role (bypasses RLS)
DO $$ BEGIN
  EXECUTE 'GRANT ALL ON ALL TABLES IN SCHEMA pmoves_core TO service_role';
EXCEPTION WHEN OTHERS THEN
  RAISE NOTICE 'GRANT to service_role on pmoves_core: %', SQLERRM;
END $$;

-- Read-only for authenticated users
DO $$ BEGIN
  EXECUTE 'GRANT SELECT ON ALL TABLES IN SCHEMA pmoves_core TO authenticated';
EXCEPTION WHEN OTHERS THEN
  RAISE NOTICE 'GRANT SELECT to authenticated on pmoves_core: %', SQLERRM;
END $$;

-- Enable RLS on each table
ALTER TABLE pmoves_core.agent ENABLE ROW LEVEL SECURITY;
ALTER TABLE pmoves_core.session ENABLE ROW LEVEL SECURITY;
ALTER TABLE pmoves_core.message ENABLE ROW LEVEL SECURITY;
ALTER TABLE pmoves_core.memory ENABLE ROW LEVEL SECURITY;
ALTER TABLE pmoves_core.event_log ENABLE ROW LEVEL SECURITY;

-- Drop any existing permissive policies (e.g., from 04_agents_avatar.sql)
DROP POLICY IF EXISTS agent_anon_all ON pmoves_core.agent;

-- Anon deny-all policies
CREATE POLICY "pmoves_core_anon_deny_agent" ON pmoves_core.agent
  FOR ALL TO anon USING (false) WITH CHECK (false);
CREATE POLICY "pmoves_core_anon_deny_session" ON pmoves_core.session
  FOR ALL TO anon USING (false) WITH CHECK (false);
CREATE POLICY "pmoves_core_anon_deny_message" ON pmoves_core.message
  FOR ALL TO anon USING (false) WITH CHECK (false);
CREATE POLICY "pmoves_core_anon_deny_memory" ON pmoves_core.memory
  FOR ALL TO anon USING (false) WITH CHECK (false);
CREATE POLICY "pmoves_core_anon_deny_event_log" ON pmoves_core.event_log
  FOR ALL TO anon USING (false) WITH CHECK (false);

-- Service role full access policies
CREATE POLICY "pmoves_core_svc_agent" ON pmoves_core.agent
  FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "pmoves_core_svc_session" ON pmoves_core.session
  FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "pmoves_core_svc_message" ON pmoves_core.message
  FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "pmoves_core_svc_memory" ON pmoves_core.memory
  FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "pmoves_core_svc_event_log" ON pmoves_core.event_log
  FOR ALL TO service_role USING (true) WITH CHECK (true);

-- Authenticated read-only policies
CREATE POLICY "pmoves_core_auth_read_agent" ON pmoves_core.agent
  FOR SELECT TO authenticated USING (true);
CREATE POLICY "pmoves_core_auth_read_session" ON pmoves_core.session
  FOR SELECT TO authenticated USING (true);
CREATE POLICY "pmoves_core_auth_read_message" ON pmoves_core.message
  FOR SELECT TO authenticated USING (true);
CREATE POLICY "pmoves_core_auth_read_memory" ON pmoves_core.memory
  FOR SELECT TO authenticated USING (true);
CREATE POLICY "pmoves_core_auth_read_event_log" ON pmoves_core.event_log
  FOR SELECT TO authenticated USING (true);
