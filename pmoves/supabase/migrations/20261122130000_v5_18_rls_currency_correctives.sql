-- v5_18 RLS / Supabase-currency correctives (audit 2026-06-30).
--
-- Idempotent remediation of stale/deprecated RLS + policy patterns found in the
-- Supabase-currency audit. NOT a refactor — same-semantics modernization to the
-- repo-canonical idiom: service access via `TO service_role` (the Postgres role,
-- which has BYPASSRLS) instead of JWT-claim checks; authenticated reads via
-- `TO authenticated`. Precedent: v5_16/v5_17, 20250115000000_service_catalog.sql:73.
--
-- Source of truth. Mirror into pmoves/supabase/migrations/ (ledgered apply path)
-- via `make db-apply-migration` / the supabase-db MCP / Z890 DB lane. All blocks
-- DROP POLICY IF EXISTS then CREATE → safe to re-run.

-- =====================================================================
-- P1 — channel_monitor: jwt_claim_role() is UNDEFINED repo-wide, so the 3
-- service_role policies in 20250204000000_channel_monitor_tables.sql abort at
-- CREATE POLICY (function does not exist) → migration fails / policies missing.
-- Recreate them as TO service_role (no undefined function). Schema: pmoves.
-- =====================================================================
DO $$
BEGIN
    IF to_regclass('pmoves.user_tokens') IS NOT NULL THEN
        DROP POLICY IF EXISTS "Service role can manage all tokens" ON pmoves.user_tokens;
        CREATE POLICY "Service role can manage all tokens" ON pmoves.user_tokens
            FOR ALL TO service_role USING (true) WITH CHECK (true);
    END IF;
    IF to_regclass('pmoves.user_sources') IS NOT NULL THEN
        DROP POLICY IF EXISTS "Service role can manage all sources" ON pmoves.user_sources;
        CREATE POLICY "Service role can manage all sources" ON pmoves.user_sources
            FOR ALL TO service_role USING (true) WITH CHECK (true);
    END IF;
    IF to_regclass('pmoves.channel_monitoring') IS NOT NULL THEN
        DROP POLICY IF EXISTS "Service role full access to monitoring" ON pmoves.channel_monitoring;
        CREATE POLICY "Service role full access to monitoring" ON pmoves.channel_monitoring
            FOR ALL TO service_role USING (true) WITH CHECK (true);
    END IF;
END $$;

-- =====================================================================
-- P2a — tokenism get_simulation_stats: SECURITY DEFINER without SET search_path
-- (search-path-injection vector; Supabase security advisor). Pin search_path.
-- =====================================================================
CREATE OR REPLACE FUNCTION pmoves_core.get_simulation_stats(simulation_uuid UUID)
RETURNS TABLE(
  week_number INTEGER,
  avg_wealth DECIMAL(18,2),
  gini_coefficient DECIMAL(10,4),
  poverty_rate DECIMAL(10,4)
) AS $$
BEGIN
  RETURN QUERY
  SELECT
    wm.week_number,
    wm.avg_wealth,
    wm.gini_coefficient,
    wm.poverty_rate
  FROM pmoves_core.simulation_weekly_metrics wm
  WHERE wm.simulation_id = simulation_uuid
  ORDER BY wm.week_number;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = pmoves_core, pg_temp;

-- P2b — tokenism simulation_summary grant: `TO public` is over-broad (public =
-- every role). Narrow to anon + authenticated (RLS/grants still gate rows).
DO $$
BEGIN
    IF to_regclass('pmoves_core.simulation_summary') IS NOT NULL THEN
        REVOKE SELECT ON pmoves_core.simulation_summary FROM PUBLIC;
        GRANT SELECT ON pmoves_core.simulation_summary TO anon, authenticated;
    END IF;
END $$;

-- =====================================================================
-- P3 — modernize auth.role() = '<role>' policies to TO-clause targeting.
-- `auth.role() = 'x'` parses the JWT per row; `TO <role>` targets the Postgres
-- role directly (correct + cheaper). Where TO already existed, the auth.role()
-- USING was redundant. Same access semantics; recreate with USING (true).
-- =====================================================================

-- 002_add_living_pages: 3 service-only policies (had NO TO clause).
DO $$
BEGIN
    IF to_regclass('pmoves_core.living_pages') IS NOT NULL THEN
        DROP POLICY IF EXISTS living_pages_service_only ON pmoves_core.living_pages;
        CREATE POLICY living_pages_service_only ON pmoves_core.living_pages
            FOR ALL TO service_role USING (true) WITH CHECK (true);
    END IF;
    IF to_regclass('pmoves_core.model_bindings') IS NOT NULL THEN
        DROP POLICY IF EXISTS model_bindings_service_only ON pmoves_core.model_bindings;
        CREATE POLICY model_bindings_service_only ON pmoves_core.model_bindings
            FOR ALL TO service_role USING (true) WITH CHECK (true);
    END IF;
    IF to_regclass('pmoves_core.swarm_attribution') IS NOT NULL THEN
        DROP POLICY IF EXISTS swarm_attribution_service_only ON pmoves_core.swarm_attribution;
        CREATE POLICY swarm_attribution_service_only ON pmoves_core.swarm_attribution
            FOR ALL TO service_role USING (true) WITH CHECK (true);
    END IF;
END $$;

-- studio_board: had TO service_role + redundant auth.role(). Drop the redundancy.
DO $$
BEGIN
    IF to_regclass('public.studio_board') IS NOT NULL THEN
        DROP POLICY IF EXISTS studio_board_service_role_all ON public.studio_board;
        CREATE POLICY studio_board_service_role_all ON public.studio_board
            FOR ALL TO service_role USING (true) WITH CHECK (true);
    END IF;
END $$;

-- youtube_control_actions: service-write had NO TO clause. (Read policy uses a
-- custom function — left as-is.)
DO $$
BEGIN
    IF to_regclass('pmoves_core.youtube_control_actions') IS NOT NULL THEN
        DROP POLICY IF EXISTS "Service write youtube control actions" ON pmoves_core.youtube_control_actions;
        CREATE POLICY "Service write youtube control actions" ON pmoves_core.youtube_control_actions
            FOR ALL TO service_role USING (true) WITH CHECK (true);
    END IF;
END $$;

-- n8n_workflow_registry: both policies had TO + redundant auth.role().
DO $$
BEGIN
    IF to_regclass('pmoves_core.n8n_workflow_registry') IS NOT NULL THEN
        DROP POLICY IF EXISTS "n8n workflow registry read" ON pmoves_core.n8n_workflow_registry;
        CREATE POLICY "n8n workflow registry read" ON pmoves_core.n8n_workflow_registry
            FOR SELECT TO authenticated USING (true);
        DROP POLICY IF EXISTS "n8n workflow registry service write" ON pmoves_core.n8n_workflow_registry;
        CREATE POLICY "n8n workflow registry service write" ON pmoves_core.n8n_workflow_registry
            FOR ALL TO service_role USING (true) WITH CHECK (true);
    END IF;
END $$;

-- model_fitness_candidates: read (authenticated) + service-write, both redundant.
DO $$
BEGIN
    IF to_regclass('pmoves_core.model_candidates') IS NOT NULL THEN
        DROP POLICY IF EXISTS "Read model candidates" ON pmoves_core.model_candidates;
        CREATE POLICY "Read model candidates" ON pmoves_core.model_candidates
            FOR SELECT TO authenticated USING (true);
        DROP POLICY IF EXISTS "Service write model candidates" ON pmoves_core.model_candidates;
        CREATE POLICY "Service write model candidates" ON pmoves_core.model_candidates
            FOR ALL TO service_role USING (true) WITH CHECK (true);
    END IF;
    IF to_regclass('pmoves_core.model_fitness_records') IS NOT NULL THEN
        DROP POLICY IF EXISTS "Read model fitness" ON pmoves_core.model_fitness_records;
        CREATE POLICY "Read model fitness" ON pmoves_core.model_fitness_records
            FOR SELECT TO authenticated USING (true);
        DROP POLICY IF EXISTS "Service write model fitness" ON pmoves_core.model_fitness_records;
        CREATE POLICY "Service write model fitness" ON pmoves_core.model_fitness_records
            FOR ALL TO service_role USING (true) WITH CHECK (true);
    END IF;
END $$;

-- archon_prompts (initdb 09): service-full-access had NO TO clause.
DO $$
BEGIN
    IF to_regclass('public.archon_prompts') IS NOT NULL THEN
        DROP POLICY IF EXISTS "Allow service role full access to archon_prompts" ON public.archon_prompts;
        CREATE POLICY "Allow service role full access to archon_prompts" ON public.archon_prompts
            FOR ALL TO service_role USING (true) WITH CHECK (true);
    END IF;
END $$;
