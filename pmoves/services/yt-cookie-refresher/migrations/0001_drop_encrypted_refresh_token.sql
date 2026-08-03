-- Migration 0001: drop encrypted_refresh_token from pmoves_core.yt_oauth_cookies
--
-- Lane 2228 refactor (2026-08-03): the Google OAuth refresh_token now lives in
-- `auth.identities` for the `darkxside@pmoves.ai` user (managed by Supabase,
-- not us). The custom `pmoves_core.yt_oauth_cookies` table only stores the
-- yt-dlp auth state (YouTube session cookies + PO token + operational status),
-- which is genuinely custom and has no Supabase equivalent.
--
-- This migration drops the now-unused `encrypted_refresh_token` column.
--
-- Pre-conditions (operator must verify before running this):
--   1. The `darkxside@pmoves.ai` user has been created in the Supabase dashboard
--      and has signed in via Google at least once (this seeds the Google
--      identity in auth.identities).
--   2. `make yt-cookies-refresh` has been run successfully with the new code
--      and reports `has_google_identity: true` in /status.
--   3. The previous column value has been read once and the new code path
--      is verified to work without it.
--
-- Rollback: not safe — once the column is dropped, any in-flight refresh that
-- still reads from it will fail. Coordinate with a maintenance window.

BEGIN;

ALTER TABLE pmoves_core.yt_oauth_cookies
    DROP COLUMN IF EXISTS encrypted_refresh_token;

COMMIT;

-- Down-migration (manual, if needed):
--   ALTER TABLE pmoves_core.yt_oauth_cookies
--       ADD COLUMN encrypted_refresh_token text;
-- (No data can be recovered; the new code path reads from auth.identities
-- not from this table.)
