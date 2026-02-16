-- Videos & transcripts (dev-friendly RLS)
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

grant select, insert, update, delete on table videos to anon;
grant select, insert, update, delete on table transcripts to anon;

alter table videos enable row level security;
alter table transcripts enable row level security;

do $$ begin
  create policy videos_anon_all on videos for all to anon using (true) with check (true);
exception when duplicate_object then null; end $$;

do $$ begin
  create policy transcripts_anon_all on transcripts for all to anon using (true) with check (true);
exception when duplicate_object then null; end $$;

