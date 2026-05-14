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

do $$ begin
  create role authenticated noinherit;
exception when duplicate_object then null; end $$;

do $$ begin
  create role service_role noinherit bypassrls;
exception when duplicate_object then
  alter role service_role bypassrls;
end $$;

grant usage on schema public to anon, authenticated, service_role;
-- Hardened RLS: no anon access to studio_board (H-03)
grant select, insert, update, delete on table studio_board to authenticated, service_role;
grant usage, select on sequence studio_board_id_seq to authenticated, service_role;

alter table studio_board enable row level security;

-- Drop permissive policies
do $$ begin
  drop policy if exists studio_board_anon_all on studio_board;
  drop policy if exists studio_board_authenticated_all on studio_board;
  drop policy if exists studio_board_service_role_all on studio_board;
exception when others then null; end $$;

-- Authenticated: full access (studio users)
do $$ begin
  create policy studio_board_authenticated_all on studio_board for all to authenticated
    using (true) with check (true);
exception when duplicate_object then null; end $$;

-- Service role: full access
do $$ begin
  create policy studio_board_service_role_all on studio_board for all to service_role
    using (true) with check (true);
exception when duplicate_object then null; end $$;

-- Anon: deny all (no policy = deny when RLS is enabled)
