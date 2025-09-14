-- Media analysis tables (dev RLS)
create table if not exists detections (
  id bigserial primary key,
  video_id text,
  ts_seconds numeric,
  label text,
  score numeric,
  frame_uri text,
  meta jsonb default '{}'::jsonb,
  created_at timestamptz default now()
);

create table if not exists segments (
  id bigserial primary key,
  video_id text,
  ts_start numeric,
  ts_end numeric,
  uri text,
  meta jsonb default '{}'::jsonb,
  created_at timestamptz default now()
);

create table if not exists emotions (
  id bigserial primary key,
  video_id text,
  ts_seconds numeric,
  label text,
  score numeric,
  meta jsonb default '{}'::jsonb,
  created_at timestamptz default now()
);

grant select, insert, update, delete on table detections, segments, emotions to anon;
alter table detections enable row level security;
alter table segments enable row level security;
alter table emotions enable row level security;
do $$ begin
  create policy det_anon_all on detections for all to anon using (true) with check (true);
exception when duplicate_object then null; end $$;
do $$ begin
  create policy seg_anon_all on segments for all to anon using (true) with check (true);
exception when duplicate_object then null; end $$;
do $$ begin
  create policy emo_anon_all on emotions for all to anon using (true) with check (true);
exception when duplicate_object then null; end $$;

