-- Geometry Swarm (CHIT) parameter packs and runs
-- Date: 2025-10-18

-- Tables
CREATE TABLE IF NOT EXISTS public.geometry_parameter_packs (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  namespace     text NOT NULL DEFAULT 'pmoves',
  modality      text NOT NULL CHECK (modality IN ('text','audio','video','image','latent','multi')),
  version       text NOT NULL,
  status        text NOT NULL DEFAULT 'draft' CHECK (status IN ('active','draft','archived')),
  cg_builder    jsonb NOT NULL DEFAULT '{}'::jsonb,
  decoder       jsonb NOT NULL DEFAULT '{}'::jsonb,
  energy        jsonb NOT NULL DEFAULT '{}'::jsonb,
  signature     text NULL,
  created_by    text NULL,
  created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_geom_param_packs_ns_mod_ver
  ON public.geometry_parameter_packs (namespace, modality, version);

CREATE INDEX IF NOT EXISTS idx_geom_param_packs_status_created
  ON public.geometry_parameter_packs (status, created_at DESC);

CREATE TABLE IF NOT EXISTS public.geometry_swarm_runs (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  population_id text NOT NULL,
  pack_id       uuid REFERENCES public.geometry_parameter_packs(id) ON DELETE SET NULL,
  best_fitness  double precision NULL,
  metrics       jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_by    text NULL,
  created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_geom_swarm_runs_population_created
  ON public.geometry_swarm_runs (population_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_geom_swarm_runs_pack
  ON public.geometry_swarm_runs (pack_id);

-- RLS with tenant isolation (namespace-based)
ALTER TABLE public.geometry_parameter_packs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.geometry_swarm_runs ENABLE ROW LEVEL SECURITY;

-- Tenant-scoped read policies for Geometry Swarm tables
-- SECURITY: Uses namespace-based tenant isolation via app.current_tenant setting
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='public' AND tablename='geometry_parameter_packs' AND policyname='read_geom_param_packs_tenant'
  ) THEN
    EXECUTE 'CREATE POLICY read_geom_param_packs_tenant ON public.geometry_parameter_packs FOR SELECT USING (namespace = current_setting(''app.current_tenant'', true) OR namespace = ''pmoves'')';
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='public' AND tablename='geometry_swarm_runs' AND policyname='read_geom_swarm_runs_tenant'
  ) THEN
    EXECUTE 'CREATE POLICY read_geom_swarm_runs_tenant ON public.geometry_swarm_runs FOR SELECT USING (pack_id IN (SELECT id FROM public.geometry_parameter_packs WHERE namespace = current_setting(''app.current_tenant'', true) OR namespace = ''pmoves''))';
  END IF;
END$$;

-- No write policies: inserts/updates/deletes require service role (bypass RLS)

