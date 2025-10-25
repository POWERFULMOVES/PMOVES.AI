-- Upload events table for tracking ingestion progress
create table if not exists upload_events (
  id bigserial primary key,
  upload_id text not null,
  filename text,
  bucket text,
  object_key text,
  status text,
  progress numeric,
  error_message text,
  size_bytes bigint,
  content_type text,
  meta jsonb default '{}'::jsonb,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create index if not exists upload_events_upload_id_idx on upload_events(upload_id);
create index if not exists upload_events_created_at_idx on upload_events(created_at desc);

-- Development-friendly grants (aligns with other tables)
grant select, insert, update, delete on table upload_events to anon;

alter table upload_events enable row level security;

do $$ begin
  create policy upload_events_open_policy on upload_events for all to anon
    using (true) with check (true);
exception when duplicate_object then null;
end $$;

-- Helper trigger to keep updated_at fresh (reuses shared helper)
create or replace function public.set_current_timestamp_updated_at()
returns trigger as $$
begin
  new.updated_at = timezone('utc', now());
  return new;
end;
$$ language plpgsql;

drop trigger if exists upload_events_touch_updated_at on upload_events;
create trigger upload_events_touch_updated_at
  before update on upload_events
  for each row
  execute function public.set_current_timestamp_updated_at();
