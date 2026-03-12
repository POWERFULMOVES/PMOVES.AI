create schema if not exists pmoves_core;

create table if not exists pmoves_core.youtube_control_actions (
  id uuid primary key,
  action text not null,
  status text not null,
  execute_requested boolean not null default false,
  request_source text not null default 'pmoves-yt',
  approved_by text,
  approval_note text,
  video_id text,
  playlist_id text,
  parent_comment_id text,
  details jsonb not null default '{}'::jsonb,
  result jsonb,
  error text,
  created_at timestamptz not null default now()
);

create index if not exists idx_youtube_control_actions_created_at
  on pmoves_core.youtube_control_actions (created_at desc);

create index if not exists idx_youtube_control_actions_action_status
  on pmoves_core.youtube_control_actions (action, status);

create index if not exists idx_youtube_control_actions_video_id
  on pmoves_core.youtube_control_actions (video_id)
  where video_id is not null;

create index if not exists idx_youtube_control_actions_playlist_id
  on pmoves_core.youtube_control_actions (playlist_id)
  where playlist_id is not null;

alter table pmoves_core.youtube_control_actions enable row level security;

drop policy if exists "Public read youtube control actions" on pmoves_core.youtube_control_actions;
create policy "Public read youtube control actions"
  on pmoves_core.youtube_control_actions for select
  using (true);

drop policy if exists "Service write youtube control actions" on pmoves_core.youtube_control_actions;
create policy "Service write youtube control actions"
  on pmoves_core.youtube_control_actions for all
  using (auth.role() = 'service_role')
  with check (auth.role() = 'service_role');

do $$
begin
  begin
    execute 'grant usage on schema pmoves_core to anon';
    execute 'grant select on pmoves_core.youtube_control_actions to anon';
  exception when undefined_object then
    null;
  end;

  begin
    execute 'grant usage on schema pmoves_core to authenticated';
    execute 'grant select on pmoves_core.youtube_control_actions to authenticated';
  exception when undefined_object then
    null;
  end;

  begin
    grant usage on schema pmoves_core to service_role;
    grant select, insert on pmoves_core.youtube_control_actions to service_role;
  exception when undefined_object then
    null;
  end;
end $$;

comment on table pmoves_core.youtube_control_actions is
  'Append-only audit trail for PMOVES.YT YouTube Data API playlist/comment control actions.';
