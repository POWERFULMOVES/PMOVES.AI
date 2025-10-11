create extension if not exists "uuid-ossp";
create extension if not exists "pgcrypto";
create extension if not exists "vector";

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

create table if not exists pmoves_core.memory (
  id uuid primary key default gen_random_uuid(),
  agent_id uuid references pmoves_core.agent(id) on delete cascade,
  kind text not null,
  key text not null,
  value jsonb not null,
  embedding vector(3584),
  created_at timestamptz default now()
);
create index if not exists memory_agent_kind_key_idx on pmoves_core.memory(agent_id, kind, key);
do $$
begin
  execute 'create index if not exists memory_embedding_idx on pmoves_core.memory using hnsw (embedding vector_l2_ops)';
exception
  when others then
    raise notice 'Skipping memory_embedding_idx creation: %', SQLERRM;
end$$;

create table if not exists pmoves_core.event_log (
  id bigserial primary key,
  occurred_at timestamptz default now(),
  session_id uuid,
  agent_id uuid,
  event_type text not null,
  payload jsonb not null
);
