-- Grant REST access to pmoves schemas for Supabase roles
DO $$
BEGIN
  -- Ensure schemas exist (no-op if already created)
  EXECUTE 'CREATE SCHEMA IF NOT EXISTS pmoves_core';
  EXECUTE 'CREATE SCHEMA IF NOT EXISTS pmoves_kb';

  -- Grant USAGE on schemas so PostgREST can introspect them
  EXECUTE 'GRANT USAGE ON SCHEMA pmoves_core TO anon, authenticated, service_role';
  EXECUTE 'GRANT USAGE ON SCHEMA pmoves_kb TO anon, authenticated, service_role';

  -- Grant SELECT on existing tables for read paths (RLS still applies where enabled)
  EXECUTE 'GRANT SELECT ON ALL TABLES IN SCHEMA pmoves_core TO anon, authenticated, service_role';
  EXECUTE 'GRANT SELECT ON ALL TABLES IN SCHEMA pmoves_kb TO anon, authenticated, service_role';

  -- Default privileges for future tables
  EXECUTE 'ALTER DEFAULT PRIVILEGES IN SCHEMA pmoves_core GRANT SELECT ON TABLES TO anon, authenticated, service_role';
  EXECUTE 'ALTER DEFAULT PRIVILEGES IN SCHEMA pmoves_kb GRANT SELECT ON TABLES TO anon, authenticated, service_role';
END $$;

