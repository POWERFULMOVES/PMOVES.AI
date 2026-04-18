-- Type: public.privacy
--
-- PostgreSQL 14 does not support `CREATE TYPE ... AS ENUM ... IF NOT EXISTS`.
-- Wrap the creation in a DO block that catches duplicate_object so the init
-- script remains idempotent on rerun (e.g., when the postgres data dir is
-- preserved but the entrypoint re-runs this file via `psql -f`).

DO $$
BEGIN
    CREATE TYPE public.privacy AS ENUM
    (
        'Public',
        'Unlisted',
        'Private'
    );
EXCEPTION
    WHEN duplicate_object THEN
        NULL;
END
$$;

-- Table: public.playlists

-- DROP TABLE public.playlists;

CREATE TABLE IF NOT EXISTS public.playlists
(
    title text,
    id text primary key,
    author text,
    description text,
    video_count integer,
    created timestamptz,
    updated timestamptz,
    privacy privacy,
    index int8[]
);

GRANT ALL ON public.playlists TO current_user;
