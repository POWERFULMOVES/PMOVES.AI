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

alter table upload_events
  add column if not exists owner_id uuid;

alter table upload_events
  alter column owner_id set default auth.uid();

do $$ begin
  alter table upload_events
    add constraint upload_events_owner_id_fkey
    foreign key (owner_id) references auth.users(id) on delete set null;
exception when duplicate_object then null;
end $$;

create index if not exists upload_events_owner_idx on upload_events(owner_id);

update upload_events
set owner_id = coalesce(owner_id, nullif(meta->>'owner_id', '')::uuid)
where owner_id is null
  and meta ? 'owner_id'
  and (meta->>'owner_id') ~* '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$';

-- Grant access to authenticated users instead of anon.
revoke all on table upload_events from anon;
grant select, insert, update, delete on table upload_events to authenticated;

alter table upload_events enable row level security;

do $$ begin
  drop policy if exists upload_events_open_policy on upload_events;
exception when undefined_object then null;
end $$;

do $$ begin
  create policy upload_events_owner_select
    on upload_events for select
    using (owner_id = auth.uid());
exception when duplicate_object then null;
end $$;

do $$ begin
  create policy upload_events_owner_modify
    on upload_events for all
    using (owner_id = auth.uid())
    with check (owner_id = auth.uid());
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
