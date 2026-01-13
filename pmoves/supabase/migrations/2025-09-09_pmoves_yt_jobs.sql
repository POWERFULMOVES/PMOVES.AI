-- PMOVES.YT job tracking tables
create table if not exists public.yt_jobs (
  id uuid primary key default gen_random_uuid(),
  type text not null check (type in ('playlist','channel')),
  args jsonb not null default '{}'::jsonb,
  state text not null default 'queued',
  started_at timestamptz,
  finished_at timestamptz,
  error text,
  created_at timestamptz not null default now()
);

create table if not exists public.yt_items (
  job_id uuid references public.yt_jobs(id) on delete cascade,
  video_id text not null,
  status text not null default 'queued',
  error text,
  retries int not null default 0,
  meta jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  primary key (job_id, video_id)
);

create index if not exists yt_items_job_idx on public.yt_items(job_id);
create index if not exists yt_items_status_idx on public.yt_items(status);

-- permissive RLS for dev; tighten for prod
alter table public.yt_jobs enable row level security;
alter table public.yt_items enable row level security;
do $$
begin
  if not exists (
    select 1 from pg_policies where schemaname='public' and tablename='yt_jobs' and policyname='yt_jobs_read') then
    create policy yt_jobs_read on public.yt_jobs for select to anon using (true);
  end if;
  if not exists (
    select 1 from pg_policies where schemaname='public' and tablename='yt_items' and policyname='yt_items_read') then
    create policy yt_items_read on public.yt_items for select to anon using (true);
  end if;
end $$;

