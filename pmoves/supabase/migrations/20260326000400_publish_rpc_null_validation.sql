-- Add missing NULL validation for p_publish_event_id in complete/fail RPCs
-- claim_studio_board_publish already validates this (line 108); align the others.
-- Follow-up from PR #1100 CodeRabbit finding

CREATE OR REPLACE FUNCTION public.complete_studio_board_publish(
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

CREATE OR REPLACE FUNCTION public.fail_studio_board_publish(
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
