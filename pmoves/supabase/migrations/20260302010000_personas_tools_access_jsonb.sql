-- Migration: Normalize personas.tools_access to JSONB capability map
-- Date: 2026-03-02
-- Purpose: Align personas schema with persona seed and JSONB GIN indexing

DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema = 'pmoves_core'
      AND table_name = 'personas'
      AND column_name = 'tools_access'
      AND data_type = 'ARRAY'
  ) THEN
    ALTER TABLE pmoves_core.personas
      ALTER COLUMN tools_access DROP DEFAULT;

    ALTER TABLE pmoves_core.personas
      ALTER COLUMN tools_access TYPE jsonb
      USING COALESCE(to_jsonb(tools_access), '{}'::jsonb);

    ALTER TABLE pmoves_core.personas
      ALTER COLUMN tools_access SET DEFAULT '{}'::jsonb;
  END IF;
END $$;

