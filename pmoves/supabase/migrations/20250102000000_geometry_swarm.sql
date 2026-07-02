-- PMOVES v5.13 geometry swarm schema (idempotent, compatible with newer geometry migrations)
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name = 'geometry_parameter_packs'
  ) THEN
    CREATE TABLE public.geometry_parameter_packs (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      namespace text NOT NULL,
      modality text NOT NULL,
      pack_type text NOT NULL DEFAULT 'cg_builder',
      status text NOT NULL DEFAULT 'draft',
      population_id text,
      generation integer,
      fitness numeric,
      energy numeric,
      params jsonb NOT NULL,
      notes text,
      created_at timestamptz NOT NULL DEFAULT timezone('UTC', now()),
      updated_at timestamptz NOT NULL DEFAULT timezone('UTC', now())
    );
  ELSE
    ALTER TABLE public.geometry_parameter_packs
      ADD COLUMN IF NOT EXISTS pack_type text DEFAULT 'cg_builder',
      ADD COLUMN IF NOT EXISTS population_id text,
      ADD COLUMN IF NOT EXISTS generation integer,
      ADD COLUMN IF NOT EXISTS fitness numeric,
      ADD COLUMN IF NOT EXISTS energy numeric,
      ADD COLUMN IF NOT EXISTS notes text,
      ADD COLUMN IF NOT EXISTS updated_at timestamptz;
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS geometry_parameter_packs_namespace_idx
    ON public.geometry_parameter_packs (namespace, modality, pack_type, status);
CREATE INDEX IF NOT EXISTS geometry_parameter_packs_created_at_idx
    ON public.geometry_parameter_packs (created_at DESC);
CREATE INDEX IF NOT EXISTS geometry_parameter_packs_pack_type_idx
    ON public.geometry_parameter_packs (pack_type);

GRANT SELECT ON public.geometry_parameter_packs TO anon, authenticated, service_role;

CREATE OR REPLACE FUNCTION public.geometry_parameter_packs_touch()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = timezone('UTC', now());
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_geometry_parameter_packs_touch ON public.geometry_parameter_packs;
CREATE TRIGGER trg_geometry_parameter_packs_touch
    BEFORE UPDATE ON public.geometry_parameter_packs
    FOR EACH ROW EXECUTE FUNCTION public.geometry_parameter_packs_touch();
