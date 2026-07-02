-- =============================================================================
-- pmoves_kb schema — initdb seed (idempotent, upgrade-safe)
-- =============================================================================
-- PostgREST exposes pmoves_kb via SUPABASE_SCHEMA / PGRST_DB_SCHEMAS, so the
-- schema MUST exist before PostgREST starts or it fails PGRST125 (schema not
-- found) on a fresh boot — before `make -C pmoves db-migrate` (db/v5_12, v5_13)
-- has had a chance to create it.
--
-- This is a DEDICATED seed file (not an edit to 00_pmoves_schema.sql) on purpose:
-- `make supabase-bootstrap` records applied seed filenames in
-- public.pmoves_bootstrap_history and SKIPS already-applied seeds, so editing an
-- existing seed would NOT run on already-bootstrapped (upgraded) databases. A new
-- filename is applied on BOTH fresh and existing databases.
--
-- Sorts after 00_0_supabase_internal.sql (which creates the anon/authenticated/
-- service_role roles) and before 00_pmoves_schema.sql. Table DDL + full REST
-- grants still land via db/v5_12 + db/v5_13; this only guarantees the schema +
-- USAGE exist early enough for PostgREST.

create schema if not exists pmoves_kb;

-- Grant USAGE to the Supabase REST roles. Guarded so a missing role (e.g. on a
-- non-Supabase Postgres) does not abort the seed run.
do $$
begin
  execute 'grant usage on schema pmoves_kb to anon, authenticated, service_role';
exception when others then
  raise notice 'pmoves_kb USAGE grant skipped: %', sqlerrm;
end $$;
