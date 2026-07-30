-- =============================================================================
-- Migration: RLS hardening for pmoves_core schema (upgrade path)
-- Defect 3: initdb RLS won't apply on upgrades (bootstrap_history skip)
-- Defect 4: CVE-2025-8713 pg_stats RLS bypass mitigation
-- =============================================================================

-- Revoke all from anon on the entire schema
DO $$ BEGIN
  EXECUTE 'REVOKE ALL ON ALL TABLES IN SCHEMA pmoves_core FROM anon';
EXCEPTION WHEN OTHERS THEN
  RAISE NOTICE 'REVOKE from anon on pmoves_core: %', SQLERRM;
END $$;

-- Grant full access to service_role (bypasses RLS)
DO $$ BEGIN
  EXECUTE 'GRANT ALL ON ALL TABLES IN SCHEMA pmoves_core TO service_role';
EXCEPTION WHEN OTHERS THEN
  RAISE NOTICE 'GRANT to service_role on pmoves_core: %', SQLERRM;
END $$;

-- Read-only for authenticated users
DO $$ BEGIN
  EXECUTE 'GRANT SELECT ON ALL TABLES IN SCHEMA pmoves_core TO authenticated';
EXCEPTION WHEN OTHERS THEN
  RAISE NOTICE 'GRANT SELECT to authenticated on pmoves_core: %', SQLERRM;
END $$;

-- Enable RLS on each table
ALTER TABLE IF EXISTS pmoves_core.agent ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS pmoves_core.session ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS pmoves_core.message ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS pmoves_core.memory ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS pmoves_core.event_log ENABLE ROW LEVEL SECURITY;

-- Drop any existing permissive policies (e.g., from 04_agents_avatar.sql)
DROP POLICY IF EXISTS agent_anon_all ON pmoves_core.agent;

-- Anon deny-all policies
-- Postgres has no CREATE POLICY IF NOT EXISTS, so each policy is dropped first
-- (DROP POLICY IF EXISTS) then re-created — idempotent and re-runnable.
DROP POLICY IF EXISTS "pmoves_core_anon_deny_agent" ON pmoves_core.agent;
CREATE POLICY "pmoves_core_anon_deny_agent" ON pmoves_core.agent
  FOR ALL TO anon USING (false) WITH CHECK (false);
DROP POLICY IF EXISTS "pmoves_core_anon_deny_session" ON pmoves_core.session;
CREATE POLICY "pmoves_core_anon_deny_session" ON pmoves_core.session
  FOR ALL TO anon USING (false) WITH CHECK (false);
DROP POLICY IF EXISTS "pmoves_core_anon_deny_message" ON pmoves_core.message;
CREATE POLICY "pmoves_core_anon_deny_message" ON pmoves_core.message
  FOR ALL TO anon USING (false) WITH CHECK (false);
DROP POLICY IF EXISTS "pmoves_core_anon_deny_memory" ON pmoves_core.memory;
CREATE POLICY "pmoves_core_anon_deny_memory" ON pmoves_core.memory
  FOR ALL TO anon USING (false) WITH CHECK (false);
DROP POLICY IF EXISTS "pmoves_core_anon_deny_event_log" ON pmoves_core.event_log;
CREATE POLICY "pmoves_core_anon_deny_event_log" ON pmoves_core.event_log
  FOR ALL TO anon USING (false) WITH CHECK (false);

-- Service role full access policies
DROP POLICY IF EXISTS "pmoves_core_svc_agent" ON pmoves_core.agent;
CREATE POLICY "pmoves_core_svc_agent" ON pmoves_core.agent
  FOR ALL TO service_role USING (true) WITH CHECK (true);
DROP POLICY IF EXISTS "pmoves_core_svc_session" ON pmoves_core.session;
CREATE POLICY "pmoves_core_svc_session" ON pmoves_core.session
  FOR ALL TO service_role USING (true) WITH CHECK (true);
DROP POLICY IF EXISTS "pmoves_core_svc_message" ON pmoves_core.message;
CREATE POLICY "pmoves_core_svc_message" ON pmoves_core.message
  FOR ALL TO service_role USING (true) WITH CHECK (true);
DROP POLICY IF EXISTS "pmoves_core_svc_memory" ON pmoves_core.memory;
CREATE POLICY "pmoves_core_svc_memory" ON pmoves_core.memory
  FOR ALL TO service_role USING (true) WITH CHECK (true);
DROP POLICY IF EXISTS "pmoves_core_svc_event_log" ON pmoves_core.event_log;
CREATE POLICY "pmoves_core_svc_event_log" ON pmoves_core.event_log
  FOR ALL TO service_role USING (true) WITH CHECK (true);

-- Authenticated read-only policies
DROP POLICY IF EXISTS "pmoves_core_auth_read_agent" ON pmoves_core.agent;
CREATE POLICY "pmoves_core_auth_read_agent" ON pmoves_core.agent
  FOR SELECT TO authenticated USING (true);
DROP POLICY IF EXISTS "pmoves_core_auth_read_session" ON pmoves_core.session;
CREATE POLICY "pmoves_core_auth_read_session" ON pmoves_core.session
  FOR SELECT TO authenticated USING (true);
DROP POLICY IF EXISTS "pmoves_core_auth_read_message" ON pmoves_core.message;
CREATE POLICY "pmoves_core_auth_read_message" ON pmoves_core.message
  FOR SELECT TO authenticated USING (true);
DROP POLICY IF EXISTS "pmoves_core_auth_read_memory" ON pmoves_core.memory;
CREATE POLICY "pmoves_core_auth_read_memory" ON pmoves_core.memory
  FOR SELECT TO authenticated USING (true);
DROP POLICY IF EXISTS "pmoves_core_auth_read_event_log" ON pmoves_core.event_log;
CREATE POLICY "pmoves_core_auth_read_event_log" ON pmoves_core.event_log
  FOR SELECT TO authenticated USING (true);

-- =============================================================================
-- CVE-2025-8713: Revoke pg_stats access from anon and authenticated roles
-- to prevent RLS bypass via statistics views
-- =============================================================================
REVOKE ALL ON ALL TABLES IN SCHEMA pg_catalog FROM anon;
REVOKE ALL ON ALL TABLES IN SCHEMA pg_catalog FROM authenticated;
REVOKE USAGE ON SCHEMA pg_catalog FROM anon;
REVOKE USAGE ON SCHEMA pg_catalog FROM authenticated;
-- Explicitly revoke pg_stats access
REVOKE SELECT ON pg_stats FROM anon;
REVOKE SELECT ON pg_stats FROM authenticated;
REVOKE SELECT ON pg_statistic FROM anon;
REVOKE SELECT ON pg_statistic FROM authenticated;
