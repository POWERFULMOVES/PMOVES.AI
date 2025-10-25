-- YouTube transcript corpus to support Jellyfin metadata backfill and PMOVES.yt search
DO $YT_TABLE$
DECLARE
  has_vector boolean := EXISTS (
    SELECT 1
    FROM pg_type
    WHERE typname = 'vector'
  );
BEGIN
  IF has_vector THEN
    EXECUTE $CREATE$
      create table if not exists youtube_transcripts (
        video_id text primary key,
        title text not null,
        description text,
        channel text,
        url text not null,
        published_at timestamptz,
        duration double precision,
        transcript text,
        embedding_st vector(384),
        embedding_gemma vector(768),
        embedding_qwen vector(2560),
        meta jsonb default '{}'::jsonb,
        created_at timestamptz default timezone('utc', now()),
        updated_at timestamptz default timezone('utc', now())
      )
    $CREATE$;
  ELSE
    EXECUTE $CREATE_F4$
      create table if not exists youtube_transcripts (
        video_id text primary key,
        title text not null,
        description text,
        channel text,
        url text not null,
        published_at timestamptz,
        duration double precision,
        transcript text,
        embedding_st float4[],
        embedding_gemma float4[],
        embedding_qwen float4[],
        meta jsonb default '{}'::jsonb,
        created_at timestamptz default timezone('utc', now()),
        updated_at timestamptz default timezone('utc', now())
      )
    $CREATE_F4$;
  END IF;
END
$YT_TABLE$;

-- Maintain updated_at automatically
create or replace function set_youtube_transcripts_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at := timezone('utc', now());
  return new;
end;
$$;

do $trigger$
begin
  if not exists (
    select 1
    from pg_trigger
    where tgname = 'youtube_transcripts_set_updated_at'
  ) then
    execute 'create trigger youtube_transcripts_set_updated_at
             before update on youtube_transcripts
             for each row execute function set_youtube_transcripts_updated_at()';
  end if;
end
$trigger$;

-- Vector index when pgvector is available
DO $YT_INDEX$
DECLARE
  has_vector boolean := EXISTS (
    SELECT 1 FROM pg_type WHERE typname = 'vector'
  );
BEGIN
  IF has_vector THEN
    BEGIN
      EXECUTE 'create index if not exists youtube_transcripts_embedding_st_idx on youtube_transcripts using ivfflat (embedding_st vector_cosine_ops) with (lists = 100)';
    EXCEPTION
      WHEN OTHERS THEN
        BEGIN
          EXECUTE 'create index if not exists youtube_transcripts_embedding_st_idx on youtube_transcripts using hnsw (embedding_st vector_cosine_ops)';
        EXCEPTION
          WHEN OTHERS THEN
            RAISE NOTICE 'Skipping vector index on youtube_transcripts.embedding_st: %', SQLERRM;
        END;
    END;

    BEGIN
      EXECUTE 'create index if not exists youtube_transcripts_embedding_gemma_idx on youtube_transcripts using ivfflat (embedding_gemma vector_cosine_ops) with (lists = 100)';
    EXCEPTION
      WHEN OTHERS THEN
        BEGIN
          EXECUTE 'create index if not exists youtube_transcripts_embedding_gemma_idx on youtube_transcripts using hnsw (embedding_gemma vector_cosine_ops)';
        EXCEPTION
          WHEN OTHERS THEN
            RAISE NOTICE 'Skipping vector index on youtube_transcripts.embedding_gemma: %', SQLERRM;
        END;
    END;

    BEGIN
      EXECUTE 'create index if not exists youtube_transcripts_embedding_qwen_idx on youtube_transcripts using ivfflat (embedding_qwen vector_cosine_ops) with (lists = 100)';
    EXCEPTION
      WHEN OTHERS THEN
        BEGIN
          EXECUTE 'create index if not exists youtube_transcripts_embedding_qwen_idx on youtube_transcripts using hnsw (embedding_qwen vector_cosine_ops)';
        EXCEPTION
          WHEN OTHERS THEN
            RAISE NOTICE 'Skipping vector index on youtube_transcripts.embedding_qwen: %', SQLERRM;
        END;
    END;
  ELSE
    RAISE NOTICE 'pgvector extension not available; skipping vector indexes on youtube_transcripts embeddings';
  END IF;
END
$YT_INDEX$;

create index if not exists youtube_transcripts_title_idx on youtube_transcripts using gin (to_tsvector('english', title));
create index if not exists youtube_transcripts_transcript_idx on youtube_transcripts using gin (to_tsvector('english', coalesce(transcript, '')));

grant select on youtube_transcripts to anon, authenticated;
grant select, insert, update, delete on youtube_transcripts to service_role;

alter table youtube_transcripts enable row level security;

do $policy$
begin
  perform 1 from pg_policies where schemaname = 'public' and tablename = 'youtube_transcripts' and policyname = 'youtube_transcripts_read_all';
  if not found then
    execute 'create policy youtube_transcripts_read_all on youtube_transcripts for select to anon using (true)';
  end if;

  perform 1 from pg_policies where schemaname = 'public' and tablename = 'youtube_transcripts' and policyname = 'youtube_transcripts_service_write';
  if not found then
    execute 'create policy youtube_transcripts_service_write on youtube_transcripts for all to service_role using (true) with check (true)';
  end if;
end
$policy$;
