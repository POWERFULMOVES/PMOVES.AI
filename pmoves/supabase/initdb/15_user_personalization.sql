-- User personalization and OAuth scaffolding for PMOVES.YT
create table if not exists pmoves.user_tokens (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users(id) on delete cascade,
  provider text not null,
  scope text[] default array[]::text[],
  refresh_token text not null,
  expires_at timestamptz,
  created_at timestamptz default timezone('utc', now()),
  updated_at timestamptz default timezone('utc', now()),
  constraint user_tokens_user_provider_key unique (user_id, provider)
);

create table if not exists pmoves.user_sources (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users(id) on delete cascade,
  provider text not null,
  source_type text not null,
  source_identifier text,
  source_url text,
  namespace text default 'pmoves',
  tags text[] default array[]::text[],
  status text default 'active',
  auto_process boolean default true,
  check_interval_minutes integer,
  filters jsonb default '{}'::jsonb,
  yt_options jsonb default '{}'::jsonb,
  config jsonb default '{}'::jsonb,
  cookies_path text,
  token_id uuid references pmoves.user_tokens(id) on delete set null,
  last_check_at timestamptz,
  last_ingest_at timestamptz,
  created_at timestamptz default timezone('utc', now()),
  updated_at timestamptz default timezone('utc', now())
);

create unique index if not exists user_sources_unique_idx
  on pmoves.user_sources (
    user_id,
    provider,
    coalesce(source_identifier, ''),
    coalesce(source_url, '')
  );

create table if not exists pmoves.user_ingest_runs (
  id bigserial primary key,
  user_source_id uuid references pmoves.user_sources(id) on delete cascade,
  video_id text not null,
  status text default 'queued',
  duration_ms integer,
  metadata jsonb default '{}'::jsonb,
  created_at timestamptz default timezone('utc', now())
);

create or replace function pmoves.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at := timezone('utc', now());
  return new;
end;
$$;

create or replace function pmoves.set_last_check_at()
returns trigger
language plpgsql
as $$
begin
  new.last_check_at := timezone('utc', now());
  if (TG_OP = 'INSERT' AND new.last_ingest_at is null) then
    new.last_ingest_at := null;
  end if;
  return new;
end;
$$;

do $$
begin
  if not exists (
    select 1
    from pg_trigger
    where tgname = 'user_sources_set_updated_at'
  ) then
    execute 'create trigger user_sources_set_updated_at before update on pmoves.user_sources for each row execute function pmoves.set_updated_at()';
  end if;
end
$$;

create index if not exists user_sources_user_provider_idx on pmoves.user_sources(user_id, provider);
create index if not exists user_sources_status_idx on pmoves.user_sources(status);
create index if not exists user_ingest_runs_source_idx on pmoves.user_ingest_runs(user_source_id);

alter table pmoves.user_tokens enable row level security;
alter table pmoves.user_sources enable row level security;
alter table pmoves.user_ingest_runs enable row level security;

do $$
begin
  if not exists (
    select 1 from pg_policies
    where schemaname = 'pmoves'
      and tablename = 'user_tokens'
      and policyname = 'user_tokens_service_write'
  ) then
    execute 'create policy user_tokens_service_write on pmoves.user_tokens for all to service_role using (true) with check (true)';
  end if;

  if not exists (
    select 1 from pg_policies
    where schemaname = 'pmoves'
      and tablename = 'user_tokens'
      and policyname = 'user_tokens_owner_read'
  ) then
    execute 'create policy user_tokens_owner_read on pmoves.user_tokens for select using (auth.uid() = user_id)';
  end if;
end
$$;

do $$
begin
  if not exists (
    select 1 from pg_policies
    where schemaname = 'pmoves'
      and tablename = 'user_sources'
      and policyname = 'user_sources_owner_manage'
  ) then
    execute 'create policy user_sources_owner_manage on pmoves.user_sources for all using (auth.uid() = user_id) with check (auth.uid() = user_id)';
  end if;

  if not exists (
    select 1 from pg_policies
    where schemaname = 'pmoves'
      and tablename = 'user_sources'
      and policyname = 'user_sources_service_write'
  ) then
    execute 'create policy user_sources_service_write on pmoves.user_sources for all to service_role using (true) with check (true)';
  end if;
end
$$;

do $$
begin
  if not exists (
    select 1 from pg_policies
    where schemaname = 'pmoves'
      and tablename = 'user_ingest_runs'
      and policyname = 'user_ingest_runs_owner_read'
  ) then
    execute 'create policy user_ingest_runs_owner_read on pmoves.user_ingest_runs for select using (
      exists (
        select 1 from pmoves.user_sources us
        where us.id = user_ingest_runs.user_source_id
          and us.user_id = auth.uid()
      )
    )';
  end if;

  if not exists (
    select 1 from pg_policies
    where schemaname = 'pmoves'
      and tablename = 'user_ingest_runs'
      and policyname = 'user_ingest_runs_service_write'
  ) then
    execute 'create policy user_ingest_runs_service_write on pmoves.user_ingest_runs for all to service_role using (true) with check (true)';
  end if;
end
$$;

grant usage on schema pmoves to anon, authenticated;
grant select on pmoves.user_tokens to authenticated;
grant select, insert, update, delete on pmoves.user_tokens to service_role;
grant select, insert, update, delete on pmoves.user_sources to service_role;
grant select, insert, update, delete on pmoves.user_sources to authenticated;
grant select, insert, update, delete on pmoves.user_ingest_runs to service_role;
