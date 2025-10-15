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
    EXECUTE $$
      create table if not exists pmoves_core.memory (
        id uuid primary key default gen_random_uuid(),
        agent_id uuid references pmoves_core.agent(id) on delete cascade,
        kind text not null,
        key text not null,
        value jsonb not null,
        embedding vector(1536),
        created_at timestamptz default now()
      )
    $$;

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

    EXECUTE 'create index if not exists memory_embedding_idx on pmoves_core.memory using ivfflat (embedding vector_cosine_ops)';
  ELSE
    EXECUTE $$
      create table if not exists pmoves_core.memory (
        id uuid primary key default gen_random_uuid(),
        agent_id uuid references pmoves_core.agent(id) on delete cascade,
        kind text not null,
        key text not null,
        value jsonb not null,
        embedding float4[],
        created_at timestamptz default now()
      )
    $$;

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
);
