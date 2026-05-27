-- Model candidates and fitness scorecards
-- Date: 2026-05-22
-- Purpose: persist Hugging Face discovery candidates and normalized TensorZero
-- fitness records before routing activation.

CREATE TABLE IF NOT EXISTS pmoves_core.model_candidates (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  model_id TEXT NOT NULL,
  hf_id TEXT NOT NULL,
  task TEXT,
  license TEXT,
  params BIGINT,
  context_length INTEGER,
  capabilities JSONB DEFAULT '[]'::jsonb,
  backend_fit JSONB DEFAULT '[]'::jsonb,
  vram_mb_estimate INTEGER,
  quantization_support JSONB DEFAULT '[]'::jsonb,
  intended_lane TEXT NOT NULL DEFAULT 'agent_mesh',
  validation_status TEXT NOT NULL DEFAULT 'candidate'
    CHECK (validation_status IN ('candidate', 'validated', 'rejected', 'activated')),
  source TEXT NOT NULL DEFAULT 'huggingface',
  agent_id TEXT NOT NULL,
  signed_trail_ref TEXT,
  metadata JSONB DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (hf_id, intended_lane)
);

CREATE TABLE IF NOT EXISTS pmoves_core.model_fitness_records (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  model_id TEXT NOT NULL,
  source TEXT NOT NULL CHECK (source IN (
    'tensorzero',
    'pinokio',
    'unsloth',
    'hf-autoresearch',
    'evoswarm',
    'manual'
  )),
  lane TEXT NOT NULL,
  score NUMERIC(7,6) NOT NULL CHECK (score >= 0 AND score <= 1),
  metrics JSONB NOT NULL DEFAULT '{}'::jsonb,
  run_id TEXT NOT NULL,
  agent_id TEXT NOT NULL,
  signature JSONB NOT NULL,
  recorded_at TIMESTAMPTZ NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (model_id, run_id)
);

CREATE INDEX IF NOT EXISTS idx_model_candidates_lane_status
  ON pmoves_core.model_candidates(intended_lane, validation_status);

CREATE INDEX IF NOT EXISTS idx_model_candidates_hf_id
  ON pmoves_core.model_candidates(hf_id);

CREATE INDEX IF NOT EXISTS idx_model_fitness_model_score
  ON pmoves_core.model_fitness_records(model_id, score DESC);

CREATE INDEX IF NOT EXISTS idx_model_fitness_lane_score
  ON pmoves_core.model_fitness_records(lane, score DESC);

ALTER TABLE pmoves_core.model_candidates ENABLE ROW LEVEL SECURITY;
ALTER TABLE pmoves_core.model_fitness_records ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Public read model candidates" ON pmoves_core.model_candidates
  FOR SELECT TO public, anon USING (true);

CREATE POLICY "Public read model fitness" ON pmoves_core.model_fitness_records
  FOR SELECT TO public, anon USING (true);

CREATE POLICY "Service write model candidates" ON pmoves_core.model_candidates
  FOR ALL TO authenticated USING (true) WITH CHECK (true);

CREATE POLICY "Service write model fitness" ON pmoves_core.model_fitness_records
  FOR ALL TO authenticated USING (true) WITH CHECK (true);
