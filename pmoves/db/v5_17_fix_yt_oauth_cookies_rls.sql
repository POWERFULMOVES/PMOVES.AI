-- v5_17 — correct yt_oauth_cookies RLS to the repo-standard role accessor.
--
-- The applied migration pmoves/supabase/migrations/20260417000000_yt_oauth_cookies.sql
-- created `yt_oauth_cookies_service_role_all` using the deprecated PostgREST GUC
-- `current_setting('request.jwt.claim.role', true)` — removed in PostgREST 9.0 and NOT
-- populated by the Supabase this repo runs, so the USING/WITH CHECK resolve empty and the
-- policy is dead code (service_role still reaches the table only via its separate BYPASSRLS).
--
-- Corrective migration (do NOT edit an already-applied migration): drop + recreate the
-- policy targeting the Postgres `service_role` role directly (TO service_role) — the
-- dependency-free idiom used by applied migrations (service_catalog.sql:73). This avoids
-- BOTH the removed `request.jwt.claim.role` GUC AND `jwt_claim_role()` (which is NOT
-- defined anywhere in repo SQL — using it would abort CREATE POLICY after the DROP,
-- leaving the table policy-less). PostgREST connects service-key requests AS service_role,
-- so TO service_role + USING(true) is the correct service-only access. Idempotent.
-- Audit ref: [[reference_supabase_rls_accessor_idiom]].

DROP POLICY IF EXISTS yt_oauth_cookies_service_role_all ON pmoves_core.yt_oauth_cookies;
CREATE POLICY yt_oauth_cookies_service_role_all
    ON pmoves_core.yt_oauth_cookies
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);
