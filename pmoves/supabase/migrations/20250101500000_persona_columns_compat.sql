-- Compatibility migration: add columns expected by v5.14 seed that are not in v5.12 personas table.
ALTER TABLE pmoves_core.personas
  ADD COLUMN IF NOT EXISTS thread_type text DEFAULT 'base',
  ADD COLUMN IF NOT EXISTS model_preference text,
  ADD COLUMN IF NOT EXISTS temperature real,
  ADD COLUMN IF NOT EXISTS max_tokens integer,
  ADD COLUMN IF NOT EXISTS system_prompt_template text,
  ADD COLUMN IF NOT EXISTS tools_access jsonb,
  ADD COLUMN IF NOT EXISTS behavior_weights jsonb,
  ADD COLUMN IF NOT EXISTS nats_subjects text[],
  ADD COLUMN IF NOT EXISTS is_active boolean DEFAULT TRUE,
  ADD COLUMN IF NOT EXISTS updated_at timestamptz NOT NULL DEFAULT now();

CREATE OR REPLACE FUNCTION pmoves_core.personas_touch_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_personas_updated_at ON pmoves_core.personas;
CREATE TRIGGER trg_personas_updated_at
  BEFORE UPDATE ON pmoves_core.personas
  FOR EACH ROW EXECUTE FUNCTION pmoves_core.personas_touch_updated_at();
