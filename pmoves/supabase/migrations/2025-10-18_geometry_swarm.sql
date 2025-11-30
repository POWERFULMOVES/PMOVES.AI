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

-- RLS (dev posture: read-only to anon; writes via service role)
ALTER TABLE public.geometry_parameter_packs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.geometry_swarm_runs ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
  DROP POLICY IF EXISTS read_geom_param_packs_all ON public.geometry_parameter_packs;
  CREATE POLICY read_geom_param_packs_all ON public.geometry_parameter_packs FOR SELECT USING (true);
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  DROP POLICY IF EXISTS read_geom_swarm_runs_all ON public.geometry_swarm_runs;
  CREATE POLICY read_geom_swarm_runs_all ON public.geometry_swarm_runs FOR SELECT USING (true);
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

