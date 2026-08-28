-- Fix nullable version in geometry_parameter_packs compat path
-- Base schema: NOT NULL. Compat migration: NULL. Resolve inconsistency.
-- Follow-up from PR #1100 CodeRabbit finding
DO $$ BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema='public' AND table_name='geometry_parameter_packs'
  ) THEN
    UPDATE public.geometry_parameter_packs SET version = 'v1' WHERE version IS NULL;
    ALTER TABLE public.geometry_parameter_packs ALTER COLUMN version SET DEFAULT 'v1';
    ALTER TABLE public.geometry_parameter_packs ALTER COLUMN version SET NOT NULL;
  END IF;
END $$;
