-- Geometry Swarm compatibility columns for geometry_parameter_packs
-- Aligns with services/common/geometry_params.py expectations
-- Date: 2025-10-18

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='geometry_parameter_packs' AND column_name='pack_type'
  ) THEN
    ALTER TABLE public.geometry_parameter_packs
      ADD COLUMN pack_type text NULL CHECK (pack_type IN ('cg_builder','decoder'));
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='geometry_parameter_packs' AND column_name='params'
  ) THEN
    ALTER TABLE public.geometry_parameter_packs
      ADD COLUMN params jsonb NOT NULL DEFAULT '{}'::jsonb;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='geometry_parameter_packs' AND column_name='version'
  ) THEN
    ALTER TABLE public.geometry_parameter_packs
      ADD COLUMN version text NULL;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='geometry_parameter_packs' AND column_name='population_id'
  ) THEN
    ALTER TABLE public.geometry_parameter_packs
      ADD COLUMN population_id text NULL;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='geometry_parameter_packs' AND column_name='generation'
  ) THEN
    ALTER TABLE public.geometry_parameter_packs
      ADD COLUMN generation integer NULL;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='geometry_parameter_packs' AND column_name='fitness'
  ) THEN
    ALTER TABLE public.geometry_parameter_packs
      ADD COLUMN fitness double precision NULL;
  END IF;
END $$;

-- Index to aid latest-active lookups by pack_type
CREATE INDEX IF NOT EXISTS idx_geom_param_packs_packtype_status_created
  ON public.geometry_parameter_packs (pack_type, status, created_at DESC);

-- geometry_swarm_runs compatibility
DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='geometry_swarm_runs' AND column_name='pack_id'
  ) THEN
    ALTER TABLE public.geometry_swarm_runs
      ADD COLUMN pack_id uuid NULL;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='geometry_swarm_runs' AND column_name='best_fitness'
  ) THEN
    ALTER TABLE public.geometry_swarm_runs
      ADD COLUMN best_fitness double precision NULL;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='geometry_swarm_runs' AND column_name='metrics'
  ) THEN
    ALTER TABLE public.geometry_swarm_runs
      ADD COLUMN metrics jsonb NOT NULL DEFAULT '{}'::jsonb;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='geometry_swarm_runs' AND column_name='created_by'
  ) THEN
    ALTER TABLE public.geometry_swarm_runs
      ADD COLUMN created_by text NULL;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='geometry_swarm_runs' AND column_name='created_at'
  ) THEN
    ALTER TABLE public.geometry_swarm_runs
      ADD COLUMN created_at timestamptz NOT NULL DEFAULT now();
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_geom_swarm_runs_pack ON public.geometry_swarm_runs (pack_id);
CREATE INDEX IF NOT EXISTS idx_geom_swarm_runs_population_created ON public.geometry_swarm_runs (population_id, created_at DESC);
