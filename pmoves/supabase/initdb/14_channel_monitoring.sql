-- Channel monitoring persistence (used by PMOVES YouTube monitor)
create schema if not exists pmoves;

create table if not exists pmoves.channel_monitoring (
  id bigserial primary key,
  channel_id text not null,
  channel_name text,
  video_id text not null,
  video_title text,
  video_url text,
  published_at timestamptz,
  discovered_at timestamptz default timezone('utc', now()),
  processed_at timestamptz,
  processing_status text default 'pending',
  priority integer default 0,
  namespace text default 'pmoves',
  tags text[],
  metadata jsonb default '{}'::jsonb,
  unique(channel_id, video_id)
);

create index if not exists channel_monitoring_status_idx
  on pmoves.channel_monitoring(processing_status);

create index if not exists channel_monitoring_channel_idx
  on pmoves.channel_monitoring(channel_id, discovered_at desc);

grant select on pmoves.channel_monitoring to anon;
grant select, insert, update, delete on pmoves.channel_monitoring to service_role;

alter table pmoves.channel_monitoring enable row level security;

do $policy$
begin
  if not exists (
    select 1
    from pg_policies
    where schemaname='pmoves'
      and tablename='channel_monitoring'
      and policyname='channel_monitoring_service_write'
  ) then
    execute 'create policy channel_monitoring_service_write on pmoves.channel_monitoring for all to service_role using (true) with check (true)';
  end if;

  if not exists (
    select 1
    from pg_policies
    where schemaname='pmoves'
      and tablename='channel_monitoring'
      and policyname='channel_monitoring_read_all'
  ) then
    execute 'create policy channel_monitoring_read_all on pmoves.channel_monitoring for select to anon using (true)';
  end if;
end
$policy$;
