-- Ensure PostgREST exposes transcripts→videos joins for Notebook sync tooling.
begin;

-- Clean up legacy duplicates so the unique constraint can be added safely.
with duplicate_videos as (
  select ctid
  from (
    select ctid,
           row_number() over (
           partition by video_id
             order by created_at nulls last,
                      ctid
           ) as rn
    from public.videos
  ) ranked
  where rn > 1
)
delete from public.videos
where ctid in (select ctid from duplicate_videos);

with duplicate_transcripts as (
  select ctid
  from (
    select ctid,
           row_number() over (
           partition by video_id
             order by created_at nulls last,
                      ctid
           ) as rn
    from public.transcripts
  ) ranked
  where rn > 1
)
delete from public.transcripts
where ctid in (select ctid from duplicate_transcripts);

delete from public.transcripts t
where t.video_id is not null
  and not exists (
    select 1
    from public.videos v
    where v.video_id = t.video_id
  );

alter table if exists public.transcripts
  drop constraint if exists transcripts_video_id_fkey;

alter table if exists public.videos
  drop constraint if exists videos_video_id_key;

alter table public.videos
  add constraint videos_video_id_key unique (video_id);

alter table public.transcripts
  add constraint transcripts_video_id_fkey
    foreign key (video_id) references public.videos(video_id) on delete cascade;

comment on constraint transcripts_video_id_fkey on public.transcripts
  is 'Allows /transcripts?select=...,videos(...) to expand YouTube metadata.';

commit;
