-- Migration: Persona Agent Creation Fields
-- Date: 2025-01-15
-- Purpose: Extend personas table to support Agent Zero/Archon agent creation
--
-- This migration adds fields to the personas table that enable:
-- - Thread type specification (base, parallel, chained, fusion, big, zero_touch)
-- - Model preference for LLM selection
-- - Temperature and token limits for generation
-- - System prompt template for agent personality
-- - Tools access list for MCP capability discovery
-- - Behavior weights for form selection
-- - NATS subjects for event subscriptions
-- - Evaluation gates configuration

-- Ensure personas table exists with base schema
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'pmoves_core'
        AND table_name = 'personas'
    ) THEN
        CREATE TABLE pmoves_core.personas (
          persona_id    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          name          text NOT NULL,
          version       text NOT NULL DEFAULT '1.0',
          description   text,
          runtime       jsonb NOT NULL DEFAULT '{}'::jsonb,
          default_packs text[] NOT NULL DEFAULT '{}',
          boosts        jsonb NOT NULL DEFAULT '{}'::jsonb,
          filters       jsonb NOT NULL DEFAULT '{}'::jsonb,
          created_at    timestamptz NOT NULL DEFAULT now()
        );

        -- Unique constraint on name + version
        ALTER TABLE pmoves_core.personas
        ADD CONSTRAINT personas_name_version_unique UNIQUE (name, version);

        RAISE NOTICE 'Created pmoves_core.personas table';
    ELSE
        RAISE NOTICE 'pmoves_core.personas table already exists';
    END IF;
END $$;

-- Add agent creation fields to personas table
DO $$
BEGIN
    -- Thread type for orchestration pattern
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'pmoves_core'
        AND table_name = 'personas'
        AND column_name = 'thread_type'
    ) THEN
        ALTER TABLE pmoves_core.personas
        ADD COLUMN thread_type text DEFAULT 'base'
        CONSTRAINT personas_thread_type_check
        CHECK (thread_type IN ('base', 'parallel', 'chained', 'fusion', 'big', 'zero_touch'));
        RAISE NOTICE 'Added thread_type column';
    END IF;

    -- Model preference for LLM selection
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'pmoves_core'
        AND table_name = 'personas'
        AND column_name = 'model_preference'
    ) THEN
        ALTER TABLE pmoves_core.personas
        ADD COLUMN model_preference text DEFAULT 'claude-sonnet-4-5';
        RAISE NOTICE 'Added model_preference column';
    END IF;

    -- Temperature for generation control
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'pmoves_core'
        AND table_name = 'personas'
        AND column_name = 'temperature'
    ) THEN
        ALTER TABLE pmoves_core.personas
        ADD COLUMN temperature float DEFAULT 0.7
        CONSTRAINT personas_temperature_check
        CHECK (temperature >= 0.0 AND temperature <= 2.0);
        RAISE NOTICE 'Added temperature column';
    END IF;

    -- Max tokens for generation limit
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'pmoves_core'
        AND table_name = 'personas'
        AND column_name = 'max_tokens'
    ) THEN
        ALTER TABLE pmoves_core.personas
        ADD COLUMN max_tokens int DEFAULT 4096
        CONSTRAINT personas_max_tokens_check
        CHECK (max_tokens > 0);
        RAISE NOTICE 'Added max_tokens column';
    END IF;

    -- System prompt template
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'pmoves_core'
        AND table_name = 'personas'
        AND column_name = 'system_prompt_template'
    ) THEN
        ALTER TABLE pmoves_core.personas
        ADD COLUMN system_prompt_template text;
        RAISE NOTICE 'Added system_prompt_template column';
    END IF;

    -- Tools access list for MCP
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'pmoves_core'
        AND table_name = 'personas'
        AND column_name = 'tools_access'
    ) THEN
        ALTER TABLE pmoves_core.personas
        ADD COLUMN tools_access text[] DEFAULT '{}';
        RAISE NOTICE 'Added tools_access column';
    END IF;

    -- Behavior weights for form selection
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'pmoves_core'
        AND table_name = 'personas'
        AND column_name = 'behavior_weights'
    ) THEN
        ALTER TABLE pmoves_core.personas
        ADD COLUMN behavior_weights jsonb DEFAULT '{"decode": 0.33, "retrieve": 0.34, "generate": 0.33}'::jsonb;
        RAISE NOTICE 'Added behavior_weights column';
    END IF;

    -- NATS subjects for event subscriptions
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'pmoves_core'
        AND table_name = 'personas'
        AND column_name = 'nats_subjects'
    ) THEN
        ALTER TABLE pmoves_core.personas
        ADD COLUMN nats_subjects text[] DEFAULT '{}';
        RAISE NOTICE 'Added nats_subjects column';
    END IF;

    -- Evaluation gates configuration
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'pmoves_core'
        AND table_name = 'personas'
        AND column_name = 'eval_gates'
    ) THEN
        ALTER TABLE pmoves_core.personas
        ADD COLUMN eval_gates jsonb DEFAULT '{
            "min_empirical_support": 0.3,
            "min_philosophical_coherence": 0.4,
            "min_integration_potential": 0.3,
            "min_description_length": 50,
            "min_proponents": 1
        }'::jsonb;
        RAISE NOTICE 'Added eval_gates column';
    END IF;

    -- Active flag for enabling/disabling personas
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'pmoves_core'
        AND table_name = 'personas'
        AND column_name = 'is_active'
    ) THEN
        ALTER TABLE pmoves_core.personas
        ADD COLUMN is_active boolean DEFAULT true;
        RAISE NOTICE 'Added is_active column';
    END IF;
END $$;

-- Create indexes for performance
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_indexes
        WHERE schemaname = 'pmoves_core'
        AND tablename = 'personas'
        AND indexname = 'idx_personas_thread_type'
    ) THEN
        CREATE INDEX idx_personas_thread_type ON pmoves_core.personas(thread_type);
        RAISE NOTICE 'Created idx_personas_thread_type';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_indexes
        WHERE schemaname = 'pmoves_core'
        AND tablename = 'personas'
        AND indexname = 'idx_personas_model_preference'
    ) THEN
        CREATE INDEX idx_personas_model_preference ON pmoves_core.personas(model_preference);
        RAISE NOTICE 'Created idx_personas_model_preference';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_indexes
        WHERE schemaname = 'pmoves_core'
        AND tablename = 'personas'
        AND indexname = 'idx_personas_active_name'
    ) THEN
        CREATE INDEX idx_personas_active_name ON pmoves_core.personas(name) WHERE is_active = true;
        RAISE NOTICE 'Created idx_personas_active_name';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_indexes
        WHERE schemaname = 'pmoves_core'
        AND tablename = 'personas'
        AND indexname = 'idx_personas_created_at'
    ) THEN
        CREATE INDEX idx_personas_created_at ON pmoves_core.personas(created_at DESC);
        RAISE NOTICE 'Created idx_personas_created_at';
    END IF;
END $$;

-- Create persona_enhancements table for modular enhancement tracking
CREATE TABLE IF NOT EXISTS pmoves_core.persona_enhancements (
    enhancement_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    persona_id uuid NOT NULL REFERENCES pmoves_core.personas(persona_id) ON DELETE CASCADE,
    enhancement_type text NOT NULL
        CONSTRAINT persona_enhancement_type_check
        CHECK (enhancement_type IN ('prompt', 'tool', 'weight', 'nats', 'model', 'eval')),
    enhancement_name text NOT NULL,
    enhancement_value jsonb NOT NULL,
    priority int DEFAULT 0,
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now()
);

-- Indexes for persona_enhancements
CREATE INDEX IF NOT EXISTS idx_persona_enhancements_persona_id
    ON pmoves_core.persona_enhancements(persona_id);
CREATE INDEX IF NOT EXISTS idx_persona_enhancements_type
    ON pmoves_core.persona_enhancements(enhancement_type);
CREATE INDEX IF NOT EXISTS idx_persona_enhancements_priority
    ON pmoves_core.persona_enhancements(priority DESC);

-- Add updated_at trigger
CREATE OR REPLACE FUNCTION pmoves_core.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_persona_enhancements_updated_at
    BEFORE UPDATE ON pmoves_core.persona_enhancements
    FOR EACH ROW
    EXECUTE FUNCTION pmoves_core.update_updated_at_column();

-- Grant permissions for PostgREST
GRANT USAGE ON SCHEMA pmoves_core TO postgrest_anon, postgrest_auth_user;
GRANT SELECT ON ALL TABLES IN SCHEMA pmoves_core TO postgrest_anon, postgrest_auth_user;

-- Allow authenticated users to insert/update personas
GRANT INSERT, UPDATE ON pmoves_core.personas TO postgrest_auth_user;
GRANT INSERT, UPDATE ON pmoves_core.persona_enhancements TO postgrest_auth_user;

COMMENT ON TABLE pmoves_core.personas IS 'Agent persona definitions for PMOVES.AI - supports Agent Zero and Archon agent creation';
COMMENT ON TABLE pmoves_core.persona_enhancements IS 'Modular enhancements for personas - supports dynamic configuration';
COMMENT ON COLUMN pmoves_core.personas.thread_type IS 'Agent orchestration pattern: base, parallel, chained, fusion, big, zero_touch';
COMMENT ON COLUMN pmoves_core.personas.model_preference IS 'Default LLM model for this persona';
COMMENT ON COLUMN pmoves_core.personas.temperature IS 'Generation temperature (0.0-2.0)';
COMMENT ON COLUMN pmoves_core.personas.max_tokens IS 'Maximum tokens for generation';
COMMENT ON COLUMN pmoves_core.personas.system_prompt_template IS 'System prompt template for agent personality';
COMMENT ON COLUMN pmoves_core.personas.tools_access IS 'List of tools this persona can access via MCP';
COMMENT ON COLUMN pmoves_core.personas.behavior_weights IS 'Weights for form selection: {decode, retrieve, generate}';
COMMENT ON COLUMN pmoves_core.personas.nats_subjects IS 'NATS subjects this persona subscribes to';
COMMENT ON COLUMN pmoves_core.personas.eval_gates IS 'Quality gate thresholds for persona evaluation';
