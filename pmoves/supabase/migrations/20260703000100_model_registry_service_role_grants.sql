-- v5_20: service_role write grants for model-registry tables
-- Date: 2026-07-03
-- Purpose: registry data-plane writes (candidate promotion, provider/model/
--   alias rows, deployments) go through PostgREST as service_role. The
--   20260115 migration created the tables but write grants for service_role
--   were incomplete, yielding 42501 on INSERT via /rest/v1.

GRANT USAGE ON SCHEMA pmoves_core TO service_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON
  pmoves_core.model_providers,
  pmoves_core.models,
  pmoves_core.model_aliases,
  pmoves_core.model_deployments,
  pmoves_core.model_candidates,
  pmoves_core.model_fitness_records
TO service_role;
GRANT SELECT ON pmoves_core.v_active_models, pmoves_core.v_active_deployments TO service_role;
