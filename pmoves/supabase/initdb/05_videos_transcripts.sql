-- Videos & transcripts (hardened RLS — H-02)
create table if not exists videos (
  id bigserial primary key,
  video_id text,
  namespace text,
  title text,
  source_url text,
  s3_base_prefix text,
  meta jsonb default '{}'::jsonb,
  created_at timestamptz default now()
);

create table if not exists transcripts (
  id bigserial primary key,
  video_id text,
  language text,
  text text,
  s3_uri text,
  meta jsonb default '{}'::jsonb,
  created_at timestamptz default now()
);

-- Anon: read-only (no INSERT/UPDATE/DELETE)
grant select on table videos to anon;
grant select on table transcripts to anon;

-- Authenticated: read-only
grant select on table videos to authenticated;
grant select on table transcripts to authenticated;

-- Service role: full access
grant all on table videos to service_role;
grant all on table transcripts to service_role;

alter table videos enable row level security;
alter table transcripts enable row level security;

-- Drop permissive anon policies
do $$ begin
  drop policy if exists videos_anon_all on videos;
  drop policy if exists transcripts_anon_all on transcripts;
exception when others then null; end $$;

-- Anon: read-only
create policy videos_anon_read on videos
  for select to anon using (true);
create policy transcripts_anon_read on transcripts
  for select to anon using (true);

-- Authenticated: read-only
create policy videos_auth_read on videos
  for select to authenticated using (true);
create policy transcripts_auth_read on transcripts
  for select to authenticated using (true);

-- Service role: full access
create policy videos_svc_all on videos
  for all to service_role using (true) with check (true);
create policy transcripts_svc_all on transcripts
  for all to service_role using (true) with check (true);
