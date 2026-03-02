-- Migration: Model Spotlight — Per-Model Analytics & Strength Profiles
-- Date: 2026-02-18
-- Purpose: Add per-model hourly metrics aggregation and computed strength profiles
-- Depends on: 20260115_model_registry.sql (model_providers, models tables)
--
-- This migration enables:
-- - Hourly aggregated per-model performance metrics (from ClickHouse via cron/n8n)
-- - Computed strength profiles for model-level comparison
-- - Convenience view joining model metadata with strength data

-- =============================================================================
-- Table: Model Metrics (hourly aggregates)
-- Stores per-model performance data aggregated from TensorZero/ClickHouse.
-- Populated by scheduled query (cron or n8n), not real-time.
-- =============================================================================
CREATE TABLE IF NOT EXISTS pmoves_core.model_metrics (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  model_id UUID NOT NULL REFERENCES pmoves_core.models(id) ON DELETE CASCADE,
  hour TIMESTAMPTZ NOT NULL,
  request_count INTEGER DEFAULT 0,
  token_input BIGINT DEFAULT 0,
  token_output BIGINT DEFAULT 0,
  avg_latency_ms NUMERIC(10,2),
  p95_latency_ms NUMERIC(10,2),
  error_count INTEGER DEFAULT 0,
  function_breakdown JSONB DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(model_id, hour)
);

COMMENT ON TABLE pmoves_core.model_metrics IS 'Hourly aggregated per-model performance metrics sourced from ClickHouse';
COMMENT ON COLUMN pmoves_core.model_metrics.hour IS 'Hour bucket (truncated to hour)';
COMMENT ON COLUMN pmoves_core.model_metrics.function_breakdown IS 'Request counts by TensorZero function, e.g. {"agent_zero": 42, "deepresearch": 7}';

CREATE INDEX IF NOT EXISTS idx_model_metrics_hour
  ON pmoves_core.model_metrics(hour DESC);
CREATE INDEX IF NOT EXISTS idx_model_metrics_model_hour
  ON pmoves_core.model_metrics(model_id, hour DESC);

-- =============================================================================
-- Table: Model Strengths (computed strength profiles)
-- One row per model. Updated periodically from aggregated metrics or seeded
-- from static configuration.
-- =============================================================================
CREATE TABLE IF NOT EXISTS pmoves_core.model_strengths (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  model_id UUID NOT NULL REFERENCES pmoves_core.models(id) ON DELETE CASCADE UNIQUE,
  total_requests BIGINT DEFAULT 0,
  total_tokens_served BIGINT DEFAULT 0,
  avg_latency_ms NUMERIC(10,2),
  uptime_pct NUMERIC(5,2),
  primary_strength TEXT,
  strength_scores JSONB,
  preferred_functions TEXT[],
  cost_efficiency_score NUMERIC(5,2),
  last_computed_at TIMESTAMPTZ DEFAULT NOW(),
  notes TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE pmoves_core.model_strengths IS 'Computed strength profiles per model — primary strength, dimensional scores, personality notes';
COMMENT ON COLUMN pmoves_core.model_strengths.primary_strength IS 'Dominant capability: reasoning, speed, coding, multilingual, creativity, context_handling';
COMMENT ON COLUMN pmoves_core.model_strengths.strength_scores IS 'Dimensional scores 0.0-1.0, e.g. {"reasoning": 0.85, "speed": 0.72, "coding": 0.91}';
COMMENT ON COLUMN pmoves_core.model_strengths.preferred_functions IS 'TensorZero functions where this model is most frequently routed';
COMMENT ON COLUMN pmoves_core.model_strengths.cost_efficiency_score IS 'Relative tokens-served-per-cost-unit score (higher = more efficient)';
COMMENT ON COLUMN pmoves_core.model_strengths.notes IS 'Tongue-in-cheek personality note — the name IS the function';

-- Trigger for updated_at (reuses function from 20260115 migration)
CREATE TRIGGER update_model_strengths_updated_at
  BEFORE UPDATE ON pmoves_core.model_strengths
  FOR EACH ROW EXECUTE FUNCTION pmoves_core.update_updated_at_column();

-- =============================================================================
-- View: Model Spotlight
-- Joins model metadata, provider info, and strength profile for dashboard use.
-- =============================================================================
CREATE OR REPLACE VIEW pmoves_core.v_model_spotlight AS
SELECT
  m.id AS model_id,
  m.name,
  m.model_id AS model_identifier,
  m.model_type,
  m.context_length,
  m.vram_mb,
  m.capabilities,
  p.name AS provider_name,
  p.type AS provider_type,
  s.total_requests,
  s.total_tokens_served,
  s.avg_latency_ms,
  s.primary_strength,
  s.strength_scores,
  s.preferred_functions,
  s.cost_efficiency_score,
  s.uptime_pct,
  s.notes,
  s.last_computed_at
FROM pmoves_core.models m
JOIN pmoves_core.model_providers p ON m.provider_id = p.id
LEFT JOIN pmoves_core.model_strengths s ON m.id = s.model_id
WHERE m.active = true;

COMMENT ON VIEW pmoves_core.v_model_spotlight IS 'Model Spotlight: active models with provider metadata and strength profiles';

-- =============================================================================
-- RLS Policies
-- =============================================================================
ALTER TABLE pmoves_core.model_metrics ENABLE ROW LEVEL SECURITY;
ALTER TABLE pmoves_core.model_strengths ENABLE ROW LEVEL SECURITY;

-- Public read for analytics dashboards
-- rllint:allow public-read - Model metrics are designed for open observability
CREATE POLICY "Public read model_metrics" ON pmoves_core.model_metrics
  FOR SELECT TO public, anon USING (true);

CREATE POLICY "Public read model_strengths" ON pmoves_core.model_strengths
  FOR SELECT TO public, anon USING (true);

-- Service account write (aggregation jobs)
-- rllint:allow authenticated-write - Aggregation jobs populate metrics
CREATE POLICY "Service write model_metrics" ON pmoves_core.model_metrics
  FOR ALL TO authenticated USING (true) WITH CHECK (true);

CREATE POLICY "Service write model_strengths" ON pmoves_core.model_strengths
  FOR ALL TO authenticated USING (true) WITH CHECK (true);

-- =============================================================================
-- Grant Permissions for PostgREST
-- =============================================================================
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'postgrest_anon') THEN
    EXECUTE 'GRANT SELECT ON pmoves_core.model_metrics TO postgrest_anon';
    EXECUTE 'GRANT SELECT ON pmoves_core.model_strengths TO postgrest_anon';
  ELSIF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
    EXECUTE 'GRANT SELECT ON pmoves_core.model_metrics TO anon';
    EXECUTE 'GRANT SELECT ON pmoves_core.model_strengths TO anon';
  END IF;

  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'postgrest_auth_user') THEN
    EXECUTE 'GRANT SELECT ON pmoves_core.model_metrics TO postgrest_auth_user';
    EXECUTE 'GRANT SELECT ON pmoves_core.model_strengths TO postgrest_auth_user';
    EXECUTE 'GRANT INSERT, UPDATE ON pmoves_core.model_metrics TO postgrest_auth_user';
    EXECUTE 'GRANT INSERT, UPDATE ON pmoves_core.model_strengths TO postgrest_auth_user';
  ELSIF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
    EXECUTE 'GRANT SELECT ON pmoves_core.model_metrics TO authenticated';
    EXECUTE 'GRANT SELECT ON pmoves_core.model_strengths TO authenticated';
    EXECUTE 'GRANT INSERT, UPDATE ON pmoves_core.model_metrics TO authenticated';
    EXECUTE 'GRANT INSERT, UPDATE ON pmoves_core.model_strengths TO authenticated';
  END IF;
END $$;

-- =============================================================================
-- Helper: Refresh model strengths from model_metrics
-- Aggregates all-time stats per model into model_strengths table.
-- Call periodically (e.g. hourly via n8n or cron).
-- =============================================================================
CREATE OR REPLACE FUNCTION pmoves_core.refresh_model_strengths()
RETURNS void AS $$
BEGIN
  INSERT INTO pmoves_core.model_strengths (
    model_id, total_requests, total_tokens_served, avg_latency_ms, last_computed_at
  )
  SELECT
    mm.model_id,
    SUM(mm.request_count),
    SUM(mm.token_input + mm.token_output),
    AVG(mm.avg_latency_ms),
    NOW()
  FROM pmoves_core.model_metrics mm
  GROUP BY mm.model_id
  ON CONFLICT (model_id) DO UPDATE SET
    total_requests = EXCLUDED.total_requests,
    total_tokens_served = EXCLUDED.total_tokens_served,
    avg_latency_ms = EXCLUDED.avg_latency_ms,
    last_computed_at = NOW();
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION pmoves_core.refresh_model_strengths IS 'Aggregate model_metrics into model_strengths. Run periodically via n8n or cron.';
