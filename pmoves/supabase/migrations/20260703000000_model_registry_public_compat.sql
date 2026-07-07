-- v5_19: public-schema compat views for model-registry service
-- Date: 2026-07-03
-- Purpose: model-registry's SupabaseClient queries unqualified relation names,
--   which PostgREST resolves against the default profile (public). The
--   registry tables/views are canonical in pmoves_core (20260115 + 20260522
--   migrations). These security_invoker views bridge the gap without
--   duplicating data or bypassing RLS. Remove if/when the service sends
--   Accept-Profile: pmoves_core headers.

CREATE OR REPLACE VIEW public.models WITH (security_invoker = true) AS
  SELECT * FROM pmoves_core.models;
CREATE OR REPLACE VIEW public.model_providers WITH (security_invoker = true) AS
  SELECT * FROM pmoves_core.model_providers;
CREATE OR REPLACE VIEW public.model_aliases WITH (security_invoker = true) AS
  SELECT * FROM pmoves_core.model_aliases;
CREATE OR REPLACE VIEW public.model_deployments WITH (security_invoker = true) AS
  SELECT * FROM pmoves_core.model_deployments;
CREATE OR REPLACE VIEW public.model_candidates WITH (security_invoker = true) AS
  SELECT * FROM pmoves_core.model_candidates;
CREATE OR REPLACE VIEW public.model_fitness_records WITH (security_invoker = true) AS
  SELECT * FROM pmoves_core.model_fitness_records;
CREATE OR REPLACE VIEW public.v_active_models WITH (security_invoker = true) AS
  SELECT * FROM pmoves_core.v_active_models;
CREATE OR REPLACE VIEW public.v_active_deployments WITH (security_invoker = true) AS
  SELECT * FROM pmoves_core.v_active_deployments;

GRANT SELECT ON public.models, public.model_providers, public.model_aliases,
  public.model_deployments, public.model_candidates,
  public.model_fitness_records, public.v_active_models,
  public.v_active_deployments TO anon, authenticated, service_role;
GRANT INSERT, UPDATE, DELETE ON public.models, public.model_providers,
  public.model_aliases, public.model_deployments, public.model_candidates,
  public.model_fitness_records TO service_role;
