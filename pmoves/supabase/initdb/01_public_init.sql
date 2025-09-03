-- Public tables for simple local testing
create table if not exists agent_memory(
  id bigserial primary key
);

create table if not exists extractions(
  id bigserial primary key
);

-- Studio board used by render-webhook
create table if not exists studio_board(
  id bigserial primary key,
  title text,
  namespace text,
  content_url text,
  status text,
  meta jsonb default '{}'::jsonb,
  created_at timestamptz default now()
);

-- Local dev roles and RLS (loose defaults; harden for prod)
do $$ begin
  create role anon noinherit;
exception when duplicate_object then null; end $$;

grant usage on schema public to anon;
grant select, insert, update, delete on table studio_board to anon;

alter table studio_board enable row level security;
do $$ begin
  create policy studio_board_anon_all on studio_board for all to anon
    using (true) with check (true);
exception when duplicate_object then null; end $$;
