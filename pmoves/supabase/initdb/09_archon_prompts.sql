-- Archon prompt catalog
-- Ensures Supabase exposes `public.archon_prompts` so Archon can load prompt
-- definitions without triggering PostgREST 205 warnings. The table mirrors
-- the upstream schema but keeps the seed data optional; PMOVES can populate
-- rows via the UI or follow-up migrations as workflows evolve.

set search_path = public;

-- Keep the timestamp helper in sync with upstream expectations.
do $$
begin
  if not exists (
    select 1
    from pg_proc
    where proname = 'update_updated_at_column'
      and pg_catalog.pg_function_is_visible(oid)
  ) then
    execute $fn$
      create function update_updated_at_column()
      returns trigger
      language plpgsql
      as $body$
      begin
        new.updated_at = timezone('utc', now());
        return new;
      end;
      $body$;
    $fn$;
  end if;
end;
$$;

-- DDL and policy wiring are only applied when we own the table. If a remote
-- environment created it with a different owner, we skip rather than fail.
do $$
declare
  rel_oid oid;
  owner_name text;
begin
  select c.oid, pg_get_userbyid(c.relowner)
    into rel_oid, owner_name
  from pg_class c
  join pg_namespace n on n.oid = c.relnamespace
  where n.nspname = 'public'
    and c.relname = 'archon_prompts';

  if rel_oid is null then
    execute $ddl$
      create table archon_prompts (
        id uuid primary key default gen_random_uuid(),
        prompt_name text unique not null,
        prompt text not null,
        description text,
        created_at timestamptz default timezone('utc', now()),
        updated_at timestamptz default timezone('utc', now())
      );
    $ddl$;
    owner_name := current_user;
    rel_oid := 'archon_prompts'::regclass;
  end if;

  if rel_oid is not null and owner_name = current_user then
    execute $ddl$create index if not exists idx_archon_prompts_name on archon_prompts(prompt_name);$ddl$;
    execute $ddl$drop trigger if exists update_archon_prompts_updated_at on archon_prompts;$ddl$;
    execute $ddl$create trigger update_archon_prompts_updated_at
          before update on archon_prompts
          for each row execute function update_updated_at_column();$ddl$;
        execute $ddl$grant all on archon_prompts to service_role;$ddl$;
        execute $ddl$grant select on archon_prompts to authenticated;$ddl$;
        execute $ddl$grant select on archon_prompts to anon;$ddl$;
    execute $ddl$alter table archon_prompts enable row level security;$ddl$;
    execute $ddl$drop policy if exists "Allow service role full access to archon_prompts" on archon_prompts;$ddl$;
    execute $ddl$create policy "Allow service role full access to archon_prompts" on archon_prompts
          for all
          using (auth.role() = 'service_role')
          with check (auth.role() = 'service_role');$ddl$;
    execute $ddl$drop policy if exists "Allow authenticated users to read archon_prompts" on archon_prompts;$ddl$;
    execute $ddl$create policy "Allow authenticated users to read archon_prompts" on archon_prompts
          for select
          to authenticated
          using (true);$ddl$;
  elsif rel_oid is not null then
    raise notice 'Skipping archon_prompts maintenance; owner is %', owner_name;
  end if;
end;
$$;

-- Optional seed rows stay in follow-up migrations; the empty table unblocks
-- Archon's prompt loader while giving PMOVES control over which prompts ship.
