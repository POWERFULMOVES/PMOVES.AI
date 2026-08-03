-- Drop the legacy public.yt_oauth_cookies stub (4 columns, 0 rows, predates
-- the migration ledger). PostgREST resolves the unqualified table name to
-- `public` first, so this stub SHADOWED pmoves_core.yt_oauth_cookies (the
-- real table, 20260417000000) and every REST upsert from the OAuth tooling
-- failed with PGRST204 "Could not find the 'access_token_expires_at' column"
-- - tokens from a completed consent flow were then discarded.
--
-- Verified before drop (2026-08-01, 5090): SELECT count(*) = 0; no migration
-- or seed creates the public-schema variant. Full context:
-- pmoves/docs/handoffs/yt-oauth-legacy-stub-drop-2026-08-01.md

DROP TABLE IF EXISTS public.yt_oauth_cookies;

-- Same YT-lane cleanup: 20260718000000_youtube_videos.sql granted DML on
-- pmoves_core.youtube_videos to the public API role. RLS (service_role-only
-- policy) already blocks every row, so the privilege was inert - but it is
-- a needless grant and trips the sql-policy-lint anon rule. Revoke it on
-- already-applied nodes; the source migration is trimmed in the same commit
-- so fresh applies never grant it.
DO $$
BEGIN
    -- Not every node has applied 20260718000000 (verified absent on 5090,
    -- 2026-08-02); guard so this migration stays universally applicable.
    IF to_regclass('pmoves_core.youtube_videos') IS NOT NULL THEN
        REVOKE ALL ON pmoves_core.youtube_videos FROM anon;
    END IF;
END $$;

-- Make PostgREST forget the stub immediately.
NOTIFY pgrst, 'reload schema';
