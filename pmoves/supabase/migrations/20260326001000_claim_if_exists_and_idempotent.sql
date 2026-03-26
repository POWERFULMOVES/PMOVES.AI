-- P1 fix: wrap bare UPDATE in IF EXISTS guard so fresh DBs without
-- studio_board do not crash during migration.
DO $$ BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name = 'studio_board'
  ) THEN
    UPDATE public.studio_board
    SET updated_at = coalesce(updated_at, created_at, now())
    WHERE updated_at IS NULL;
  END IF;
END $$;

-- P1 fix: replace claim_studio_board_publish with idempotent variant.
-- Previously the WHERE clause re-ran the full UPDATE on rows already in
-- 'publishing' status with the same publish_request_id, creating a TOCTOU
-- race window.  The new version checks for already-claimed rows first and
-- returns true (no-op) without touching the row.
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

  -- Idempotency: already claimed with this request_id -> no-op success
  if exists (
    select 1 from public.studio_board
    where id = p_row_id
      and status = 'publishing'
      and coalesce(meta->>'publish_request_id', '') = p_publish_event_id
  ) then
    return true;
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
    and status = 'approved';

  get diagnostics updated_rows = row_count;
  return updated_rows > 0;
end;
$$;
