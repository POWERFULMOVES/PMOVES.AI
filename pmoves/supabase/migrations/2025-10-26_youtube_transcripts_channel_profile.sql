-- Enrich youtube_transcripts with channel profile fields surfaced by channel monitor.
begin;

alter table public.youtube_transcripts
  add column if not exists channel_id text;

alter table public.youtube_transcripts
  add column if not exists channel_url text;

alter table public.youtube_transcripts
  add column if not exists channel_thumbnail text;

alter table public.youtube_transcripts
  add column if not exists channel_tags text[];

alter table public.youtube_transcripts
  add column if not exists namespace text;

alter table public.youtube_transcripts
  add column if not exists channel_metadata jsonb default '{}'::jsonb;

alter table public.youtube_transcripts
  alter column channel_metadata set default '{}'::jsonb;

update public.youtube_transcripts
  set channel_metadata = '{}'::jsonb
  where channel_metadata is null;

create index if not exists youtube_transcripts_channel_idx
  on public.youtube_transcripts(channel_id);

create index if not exists youtube_transcripts_namespace_idx
  on public.youtube_transcripts(namespace);

commit;
