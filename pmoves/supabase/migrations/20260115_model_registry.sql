-- Migration: Model Registry for Dynamic Model Configuration
-- Date: 2025-01-15
-- Purpose: Create Supabase-backed model registry following service discovery pattern
--
-- This migration enables:
-- - Dynamic model configuration without hardcoded values
-- - GPU orchestrator integration with Supabase
-- - TensorZero TOML generation from database
-- - Model deployment tracking across GPU nodes

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =============================================================================
-- Table: Model Providers
-- Tracks LLM/API providers (OpenAI, Anthropic, Ollama, vLLM, etc.)
-- =============================================================================
CREATE TABLE IF NOT EXISTS pmoves_core.model_providers (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL UNIQUE,
  type TEXT NOT NULL CHECK (type IN ('openai_compatible', 'anthropic', 'ollama', 'vllm', 'custom')),
  api_base TEXT,
  api_key_env_var TEXT,
  description TEXT,
  metadata JSONB DEFAULT '{}'::jsonb,
  active BOOLEAN DEFAULT true,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE pmoves_core.model_providers IS 'LLM/API provider configurations for dynamic model routing';
COMMENT ON COLUMN pmoves_core.model_providers.type IS 'Provider type: openai_compatible, anthropic, ollama, vllm, custom';
COMMENT ON COLUMN pmoves_core.model_providers.api_base IS 'Base URL for API requests';
COMMENT ON COLUMN pmoves_core.model_providers.api_key_env_var IS 'Environment variable name containing API key';

-- =============================================================================
-- Table: Models
-- Tracks individual LLMs, embedding models, and other AI models
-- =============================================================================
CREATE TABLE IF NOT EXISTS pmoves_core.models (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  provider_id UUID NOT NULL REFERENCES pmoves_core.model_providers(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  model_id TEXT NOT NULL,  -- e.g., "qwen3:8b", "gpt-4o-mini", "claude-sonnet-4-5"
  model_type TEXT NOT NULL CHECK (model_type IN ('chat', 'embedding', 'reranker', 'vl', 'tts', 'audio', 'image')),
  capabilities JSONB DEFAULT '[]'::jsonb,  -- ["function_calling", "vision", "json_mode"]
  vram_mb INTEGER DEFAULT 0,
  context_length INTEGER,
  description TEXT,
  metadata JSONB DEFAULT '{}'::jsonb,
  active BOOLEAN DEFAULT true,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(provider_id, model_id)
);

COMMENT ON TABLE pmoves_core.models IS 'Individual AI model definitions with capabilities and resource requirements';
COMMENT ON COLUMN pmoves_core.models.model_type IS 'Model category: chat, embedding, reranker, vl (vision-language), tts, audio, image';
COMMENT ON COLUMN pmoves_core.models.vram_mb IS 'VRAM required in MB for local models';
COMMENT ON COLUMN pmoves_core.models.context_length IS 'Maximum context window in tokens';

-- =============================================================================
-- Table: Model Aliases
-- UI-friendly naming and context-specific model references
-- =============================================================================
CREATE TABLE IF NOT EXISTS pmoves_core.model_aliases (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  model_id UUID NOT NULL REFERENCES pmoves_core.models(id) ON DELETE CASCADE,
  alias TEXT NOT NULL,
  context TEXT,  -- e.g., "agent_zero", "deepresearch", "coding", "default"
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(model_id, context)
);

COMMENT ON TABLE pmoves_core.model_aliases IS 'Model aliases for UI-friendly naming and context-specific references';

-- =============================================================================
-- Table: Service Model Mappings
-- Maps PMOVES services/functions to models (replaces hardcoded TensorZero config)
-- =============================================================================
CREATE TABLE IF NOT EXISTS pmoves_core.service_model_mappings (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  service_name TEXT NOT NULL,  -- e.g., "agent_zero", "deepresearch", "tensorzero"
  function_name TEXT NOT NULL,  -- e.g., "chat", "embeddings", "orchestration"
  model_id UUID NOT NULL REFERENCES pmoves_core.models(id) ON DELETE CASCADE,
  variant_name TEXT NOT NULL,  -- e.g., "fast", "accurate", "local", "cloud"
  priority INTEGER DEFAULT 5,  -- Lower = higher priority
  weight DECIMAL(3,2) DEFAULT 1.0,  -- For weighted routing
  fallback_model_id UUID REFERENCES pmoves_core.models(id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(service_name, function_name, variant_name)
);

COMMENT ON TABLE pmoves_core.service_model_mappings IS 'Service-to-model mappings for dynamic routing (replaces hardcoded TensorZero variants)';
COMMENT ON COLUMN pmoves_core.service_model_mappings.weight IS 'Routing weight (0.0-1.0) for weighted A/B testing';

-- =============================================================================
-- Table: Model Deployments
-- Tracks which models are loaded on which GPU nodes
-- =============================================================================
CREATE TABLE IF NOT EXISTS pmoves_core.model_deployments (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  model_id UUID NOT NULL REFERENCES pmoves_core.models(id) ON DELETE CASCADE,
  node_id TEXT NOT NULL,  -- Hostname or node identifier
  provider_type TEXT CHECK (provider_type IN ('ollama', 'vllm', 'tts', 'custom')),
  status TEXT CHECK (status IN ('loading', 'loaded', 'unloaded', 'error')),
  vram_allocated_mb INTEGER,
  loaded_at TIMESTAMPTZ,
  last_used_at TIMESTAMPTZ,
  error_message TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE pmoves_core.model_deployments IS 'Live tracking of model deployments across GPU nodes';

-- =============================================================================
-- Indexes for Performance
-- =============================================================================
CREATE INDEX IF NOT EXISTS idx_models_provider ON pmoves_core.models(provider_id);
CREATE INDEX IF NOT EXISTS idx_models_type_active ON pmoves_core.models(model_type, active);
CREATE INDEX IF NOT EXISTS idx_models_active_type ON pmoves_core.models(active) WHERE active = true;
CREATE INDEX IF NOT EXISTS idx_mappings_service ON pmoves_core.service_model_mappings(service_name, function_name);
CREATE INDEX IF NOT EXISTS idx_mappings_model ON pmoves_core.service_model_mappings(model_id);
CREATE INDEX IF NOT EXISTS idx_deployments_node_status ON pmoves_core.model_deployments(node_id, status);
CREATE INDEX IF NOT EXISTS idx_deployments_model_status ON pmoves_core.model_deployments(model_id, status);
CREATE INDEX IF NOT EXISTS idx_providers_active ON pmoves_core.model_providers(active) WHERE active = true;

-- =============================================================================
-- Views for Convenience
-- =============================================================================

-- Active models with provider details
CREATE OR REPLACE VIEW pmoves_core.v_active_models AS
SELECT
  m.id,
  m.name,
  m.model_id,
  m.model_type,
  m.capabilities,
  m.vram_mb,
  m.context_length,
  m.description,
  p.id as provider_id,
  p.name as provider_name,
  p.type as provider_type,
  p.api_base,
  p.api_key_env_var,
  json_agg(DISTINCT jsonb_build_object(
    'alias', a.alias,
    'context', a.context
  ) ORDER BY a.context) as aliases
FROM pmoves_core.models m
JOIN pmoves_core.model_providers p ON m.provider_id = p.id
LEFT JOIN pmoves_core.model_aliases a ON m.id = a.model_id
WHERE m.active = true AND p.active = true
GROUP BY m.id, p.id;

COMMENT ON VIEW pmoves_core.v_active_models IS 'Active models with provider details and aliases';

-- Service model mappings with full details
CREATE OR REPLACE VIEW pmoves_core.v_service_models AS
SELECT
  s.service_name,
  s.function_name,
  s.variant_name,
  s.priority,
  s.weight,
  m.model_id,
  m.name as model_name,
  m.model_type,
  m.vram_mb,
  m.context_length,
  p.name as provider_name,
  p.type as provider_type,
  p.api_base,
  fm.model_id as fallback_model_id,
  fm.name as fallback_model_name
FROM pmoves_core.service_model_mappings s
JOIN pmoves_core.models m ON s.model_id = m.id
JOIN pmoves_core.model_providers p ON m.provider_id = p.id
LEFT JOIN pmoves_core.models fm ON s.fallback_model_id = fm.id;

COMMENT ON VIEW pmoves_core.v_service_models IS 'Service-to-model mappings with full model and provider details';

-- Active deployments by node
CREATE OR REPLACE VIEW pmoves_core.v_active_deployments AS
SELECT
  d.node_id,
  d.provider_type,
  d.status,
  d.vram_allocated_mb,
  d.loaded_at,
  d.last_used_at,
  json_agg(jsonb_build_object(
    'model_id', m.model_id,
    'model_name', m.name,
    'model_type', m.model_type,
    'provider', p.name
  ) ORDER BY m.model_type, m.name) as models
FROM pmoves_core.model_deployments d
JOIN pmoves_core.models m ON d.model_id = m.id
JOIN pmoves_core.model_providers p ON m.provider_id = p.id
WHERE d.status = 'loaded'
GROUP BY d.node_id, d.provider_type, d.status, d.vram_allocated_mb, d.loaded_at, d.last_used_at;

COMMENT ON VIEW pmoves_core.v_active_deployments IS 'Active model deployments grouped by node';

-- =============================================================================
-- RLS (Row Level Security) Policies
-- =============================================================================

-- Enable RLS on all tables
ALTER TABLE pmoves_core.model_providers ENABLE ROW LEVEL SECURITY;
ALTER TABLE pmoves_core.models ENABLE ROW LEVEL SECURITY;
ALTER TABLE pmoves_core.model_aliases ENABLE ROW LEVEL SECURITY;
ALTER TABLE pmoves_core.service_model_mappings ENABLE ROW LEVEL SECURITY;
ALTER TABLE pmoves_core.model_deployments ENABLE ROW LEVEL SECURITY;

-- Public read access for model discovery
-- rllint:allow public-read - Model registry is designed for open discovery
CREATE POLICY "Public read providers" ON pmoves_core.model_providers
  FOR SELECT TO public, anon USING (true);

CREATE POLICY "Public read models" ON pmoves_core.models
  FOR SELECT TO public, anon USING (true);

CREATE POLICY "Public read aliases" ON pmoves_core.model_aliases
  FOR SELECT TO public, anon USING (true);

CREATE POLICY "Public read mappings" ON pmoves_core.service_model_mappings
  FOR SELECT TO public, anon USING (true);

CREATE POLICY "Public read deployments" ON pmoves_core.model_deployments
  FOR SELECT TO public, anon USING (true);

-- Service account write access
-- rllint:allow authenticated-write - Services manage model configuration
CREATE POLICY "Service write providers" ON pmoves_core.model_providers
  FOR ALL TO authenticated USING (true) WITH CHECK (true);

CREATE POLICY "Service write models" ON pmoves_core.models
  FOR ALL TO authenticated USING (true) WITH CHECK (true);

CREATE POLICY "Service write aliases" ON pmoves_core.model_aliases
  FOR ALL TO authenticated USING (true) WITH CHECK (true);

CREATE POLICY "Service write mappings" ON pmoves_core.service_model_mappings
  FOR ALL TO authenticated USING (true) WITH CHECK (true);

CREATE POLICY "Service write deployments" ON pmoves_core.model_deployments
  FOR ALL TO authenticated USING (true) WITH CHECK (true);

-- =============================================================================
-- Trigger for updated_at
-- =============================================================================
CREATE OR REPLACE FUNCTION pmoves_core.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_providers_updated_at
  BEFORE UPDATE ON pmoves_core.model_providers
  FOR EACH ROW EXECUTE FUNCTION pmoves_core.update_updated_at_column();

CREATE TRIGGER update_models_updated_at
  BEFORE UPDATE ON pmoves_core.models
  FOR EACH ROW EXECUTE FUNCTION pmoves_core.update_updated_at_column();

-- =============================================================================
-- Grant Permissions for PostgREST
-- =============================================================================
GRANT USAGE ON SCHEMA pmoves_core TO postgrest_anon, postgrest_auth_user;
GRANT SELECT ON ALL TABLES IN SCHEMA pmoves_core TO postgrest_anon, postgrest_auth_user;
GRANT INSERT, UPDATE ON ALL TABLES IN SCHEMA pmoves_core TO postgrest_auth_user;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA pmoves_core TO postgrest_anon, postgrest_auth_user;

-- =============================================================================
-- Helper Functions
-- =============================================================================

-- Function to get model by alias/context
CREATE OR REPLACE FUNCTION pmoves_core.get_model_by_alias(
  p_alias TEXT,
  p_context TEXT DEFAULT NULL
) RETURNS TABLE (
  model_id UUID,
  model_name TEXT,
  provider_name TEXT,
  api_base TEXT
) AS $$
BEGIN
  RETURN QUERY
  SELECT
    m.id,
    m.name,
    p.name,
    p.api_base
  FROM pmoves_core.model_aliases a
  JOIN pmoves_core.models m ON a.model_id = m.id
  JOIN pmoves_core.model_providers p ON m.provider_id = p.id
  WHERE a.alias = p_alias
    AND (p_context IS NULL OR a.context = p_context)
    AND m.active = true
    AND p.active = true
  LIMIT 1;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION pmoves_core.get_model_by_alias IS 'Retrieve model by alias with optional context filter';

-- Function to get models for a service/function
CREATE OR REPLACE FUNCTION pmoves_core.get_service_models(
  p_service_name TEXT,
  p_function_name TEXT DEFAULT NULL
) RETURNS TABLE (
  model_id UUID,
  model_name TEXT,
  variant_name TEXT,
  priority INTEGER,
  weight NUMERIC,
  fallback_model_id UUID
) AS $$
BEGIN
  RETURN QUERY
  SELECT
    m.id,
    m.name,
    s.variant_name,
    s.priority,
    s.weight,
    s.fallback_model_id
  FROM pmoves_core.service_model_mappings s
  JOIN pmoves_core.models m ON s.model_id = m.id
  WHERE s.service_name = p_service_name
    AND (p_function_name IS NULL OR s.function_name = p_function_name)
    AND m.active = true
  ORDER BY s.priority ASC, s.variant_name;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION pmoves_core.get_service_models IS 'Retrieve models mapped to a service/function ordered by priority';
