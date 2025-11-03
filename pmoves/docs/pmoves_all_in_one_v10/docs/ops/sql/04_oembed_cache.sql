create table if not exists oembed_cache (
  provider text not null,
  key text not null,
  data jsonb not null,
  fetched_at timestamptz not null default now(),
  primary key (provider, key)
);
alter table oembed_cache enable row level security;
create policy if not exists "oembed read" on oembed_cache for select using ( true );
create policy if not exists "oembed write svc" on oembed_cache for insert with check ( auth.role() = 'service_role' );
create policy if not exists "oembed upsert svc" on oembed_cache for update using ( auth.role() = 'service_role' ) with check ( auth.role() = 'service_role' );