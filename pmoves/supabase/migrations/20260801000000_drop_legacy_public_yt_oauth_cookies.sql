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

-- Make PostgREST forget the stub immediately.
NOTIFY pgrst, 'reload schema';
