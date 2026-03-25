alter table if exists public.studio_board
  add column if not exists updated_at timestamptz default now();

update public.studio_board
set updated_at = coalesce(updated_at, created_at, now())
where updated_at is null;

create or replace function public.set_studio_board_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at := now();
  return new;
end;
$$;

drop trigger if exists studio_board_touch_updated_at on public.studio_board;
create trigger studio_board_touch_updated_at
before update on public.studio_board
for each row
execute function public.set_studio_board_updated_at();

create table if not exists public.publisher_audit (
  publish_event_id text primary key,
  studio_board_id bigint references public.studio_board(id) on delete set null,
  approval_event_ts timestamptz,
  correlation_id text,
  artifact_uri text,
  artifact_path text,
  namespace text,
  reviewer text,
  reviewed_at timestamptz,
  status text not null check (status in ('published', 'failed')),
  failure_reason text,
  published_event_id text,
  public_url text,
  published_at timestamptz,
  processed_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  meta jsonb not null default '{}'::jsonb
);

create index if not exists idx_publisher_audit_status on public.publisher_audit(status);
create index if not exists idx_publisher_audit_artifact_path on public.publisher_audit(artifact_path);
create index if not exists idx_publisher_audit_namespace on public.publisher_audit(namespace);
create index if not exists idx_publisher_audit_reviewer on public.publisher_audit(reviewer);
create index if not exists idx_publisher_audit_processed_at on public.publisher_audit(processed_at desc);
create index if not exists idx_publisher_audit_studio_board_id on public.publisher_audit(studio_board_id);

create or replace function public.set_publisher_audit_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at := now();
  return new;
end;
$$;

drop trigger if exists publisher_audit_touch_updated_at on public.publisher_audit;
create trigger publisher_audit_touch_updated_at
before update on public.publisher_audit
for each row
execute function public.set_publisher_audit_updated_at();

create table if not exists public.publisher_metrics_rollup (
  artifact_uri text primary key,
  namespace text,
  slug text,
  published_at timestamptz,
  turnaround_seconds double precision,
  approval_latency_seconds double precision,
  engagement jsonb,
  cost jsonb
);

create table if not exists public.publisher_discord_metrics (
  published_event_id text primary key,
  artifact_uri text,
  namespace text,
  slug text,
  published_at timestamptz,
  turnaround_seconds double precision,
  approval_latency_seconds double precision,
  engagement jsonb,
  cost jsonb,
  event_topic text,
  channel text,
  webhook_success boolean
);

create index if not exists idx_publisher_discord_metrics_published_at
  on public.publisher_discord_metrics(published_at desc);

create or replace function public.claim_studio_board_publish(
  p_row_id bigint,
  p_publish_event_id text,
  p_requested_at timestamptz default now()
) returns boolean
language plpgsql
security definer
set search_path = public
as $$
declare
  updated_rows integer := 0;
begin
  if p_row_id is null or p_publish_event_id is null or btrim(p_publish_event_id) = '' then
    return false;
  end if;

  update public.studio_board
  set status = 'publishing',
      meta = (
        (
          coalesce(meta, '{}'::jsonb)
          - 'publish_failed_at'
          - 'publish_failure_reason'
          - 'publish_failure_stage'
          - 'publish_failure_meta'
        )
        || jsonb_build_object(
          'studio_board_id', id,
          'publish_state', 'publishing',
          'publish_request_id', p_publish_event_id,
          'publish_requested_at', p_requested_at,
          'publish_request_source', 'publisher'
        )
      )
  where id = p_row_id
    and coalesce(meta->>'publish_event_sent_at', '') = ''
    and (
      status = 'approved'
      or (
        status = 'publishing'
        and coalesce(meta->>'publish_request_id', '') = p_publish_event_id
      )
    );

  get diagnostics updated_rows = row_count;
  return updated_rows > 0;
end;
$$;

create or replace function public.complete_studio_board_publish(
  p_row_id bigint,
  p_publish_event_id text,
  p_published_event_id text,
  p_published_at timestamptz default now(),
  p_publish_meta jsonb default '{}'::jsonb
) returns boolean
language plpgsql
security definer
set search_path = public
as $$
declare
  updated_rows integer := 0;
begin
  if p_row_id is null or p_publish_event_id is null or btrim(p_publish_event_id) = '' then
    return false;
  end if;

  update public.studio_board
  set status = 'published',
      meta = (
        (
          coalesce(meta, '{}'::jsonb)
          - 'publish_failed_at'
          - 'publish_failure_reason'
          - 'publish_failure_stage'
          - 'publish_failure_meta'
        )
        || jsonb_build_object(
          'studio_board_id', id,
          'publish_state', 'published',
          'publish_request_id', p_publish_event_id,
          'publish_event_sent_at', p_published_at,
          'published_at', p_published_at,
          'published_event_id', p_published_event_id
        )
        || coalesce(p_publish_meta, '{}'::jsonb)
      )
  where id = p_row_id
    and (
      status in ('approved', 'publishing')
      or (
        status = 'published'
        and coalesce(meta->>'publish_request_id', '') = coalesce(p_publish_event_id, '')
      )
    );

  get diagnostics updated_rows = row_count;
  return updated_rows > 0;
end;
$$;

create or replace function public.fail_studio_board_publish(
  p_row_id bigint,
  p_publish_event_id text,
  p_stage text,
  p_reason text,
  p_failed_at timestamptz default now(),
  p_failure_meta jsonb default '{}'::jsonb
) returns boolean
language plpgsql
security definer
set search_path = public
as $$
declare
  updated_rows integer := 0;
begin
  if p_row_id is null or p_publish_event_id is null or btrim(p_publish_event_id) = '' then
    return false;
  end if;

  update public.studio_board
  set status = 'publish_failed',
      meta = (
        (
          coalesce(meta, '{}'::jsonb)
          - 'publish_request_id'
          - 'publish_requested_at'
          - 'publish_request_source'
        )
        || jsonb_build_object(
          'studio_board_id', id,
          'publish_state', 'failed',
          'last_publish_request_id', p_publish_event_id,
          'publish_failed_at', p_failed_at,
          'publish_failure_stage', coalesce(p_stage, 'unknown'),
          'publish_failure_reason', coalesce(nullif(btrim(p_reason), ''), 'unspecified failure'),
          'publish_failure_meta', coalesce(p_failure_meta, '{}'::jsonb)
        )
      )
  where id = p_row_id
    and coalesce(meta->>'publish_event_sent_at', '') = ''
    and (
      status in ('approved', 'publishing')
      or (
        status = 'publish_failed'
        and coalesce(meta->>'last_publish_request_id', '') = coalesce(p_publish_event_id, '')
      )
    );

  get diagnostics updated_rows = row_count;
  return updated_rows > 0;
end;
$$;

grant select, insert, update on table public.publisher_audit to service_role;
grant select, insert, update on table public.publisher_metrics_rollup to service_role;
grant select, insert, update on table public.publisher_discord_metrics to service_role;
grant execute on function public.claim_studio_board_publish(bigint, text, timestamptz) to service_role;
grant execute on function public.complete_studio_board_publish(bigint, text, text, timestamptz, jsonb) to service_role;
grant execute on function public.fail_studio_board_publish(bigint, text, text, text, timestamptz, jsonb) to service_role;
