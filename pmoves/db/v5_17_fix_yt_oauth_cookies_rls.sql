-- v5_17 — correct yt_oauth_cookies RLS to the repo-standard role accessor.
--
-- The applied migration pmoves/supabase/migrations/20260417000000_yt_oauth_cookies.sql
-- created `yt_oauth_cookies_service_role_all` using the deprecated PostgREST GUC
-- `current_setting('request.jwt.claim.role', true)` — removed in PostgREST 9.0 and NOT
-- populated by the Supabase this repo runs, so the USING/WITH CHECK resolve empty and the
-- policy is dead code (service_role still reaches the table only via its separate BYPASSRLS).
--
-- Corrective migration (do NOT edit an already-applied migration): drop + recreate the
-- policy with the repo-standard helper `jwt_claim_role()` used by the applied migrations
-- (pmoves/supabase/migrations/20250204000000_channel_monitor_tables.sql:105). Idempotent.
-- Audit ref: [[reference_supabase_rls_accessor_idiom]].

DROP POLICY IF EXISTS yt_oauth_cookies_service_role_all ON pmoves_core.yt_oauth_cookies;
CREATE POLICY yt_oauth_cookies_service_role_all
    ON pmoves_core.yt_oauth_cookies
    FOR ALL
    USING (jwt_claim_role() = 'service_role')
    WITH CHECK (jwt_claim_role() = 'service_role');
