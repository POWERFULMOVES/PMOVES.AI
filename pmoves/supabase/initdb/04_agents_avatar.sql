-- Expose agents with avatar_url for UI and assign operations
alter table if exists pmoves_core.agent
  add column if not exists avatar_url text;

-- Local dev grants and permissive RLS (do not use in prod)
grant select, insert, update, delete on table pmoves_core.agent to anon;
alter table pmoves_core.agent enable row level security;
do $$ begin
  create policy agent_anon_all on pmoves_core.agent for all to anon using (true) with check (true);
exception when duplicate_object then null; end $$;
