-- Ensure PostgREST exposes transcripts→videos joins for Notebook sync tooling.
begin;

alter table public.videos
  add constraint videos_video_id_key unique (video_id);

alter table public.transcripts
  add constraint transcripts_video_id_fkey
    foreign key (video_id) references public.videos(video_id) on delete cascade;

comment on constraint transcripts_video_id_fkey on public.transcripts
  is 'Allows /transcripts?select=...,videos(...) to expand YouTube metadata.';

commit;
