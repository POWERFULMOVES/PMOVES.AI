-- v5_21: public-schema compat view for the service-model mapping
-- Date: 2026-07-05
-- Purpose: the v5_19 compat migration (20260703000000) bridged public.models,
--   public.v_active_models, public.v_active_deployments, etc. into the default
--   PostgREST profile but omitted v_service_models. SupabaseClient.get_service_models()
--   and GET /api/services/{service}/models query v_service_models UNQUALIFIED, so
--   PostgREST resolves public.v_service_models and 404s without this view. This
--   is a follow-on additive migration (v5_19 is already applied on live DBs, so
--   the view is added here rather than by editing the ledgered migration).
--   Mirrors the security_invoker + grant pattern of the v_active_models /
--   v_active_deployments compat views (v5_19 public view + v5_20 schema grant).

CREATE OR REPLACE VIEW public.v_service_models WITH (security_invoker = true) AS
  SELECT * FROM pmoves_core.v_service_models;

-- Public compat grant — mirrors v5_19's SELECT grants on the sibling views.
GRANT SELECT ON public.v_service_models TO anon, authenticated, service_role;
-- Underlying-relation grant — mirrors v5_20's
-- `GRANT SELECT ON pmoves_core.v_active_models, v_active_deployments TO service_role`.
-- security_invoker checks privileges as the invoking role, so service_role needs
-- SELECT on the canonical pmoves_core view for the compat view to resolve.
GRANT SELECT ON pmoves_core.v_service_models TO service_role;
