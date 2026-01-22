-- PMOVES v5.13: Persona Enhancements Table
-- Purpose: Modular enhancement tracking for personas
--
-- This table stores persona enhancements that can be dynamically applied
-- to agent creation, allowing for fine-grained control without modifying
-- the core persona definition.
--
-- Enhancement Types:
--   - prompt: Additional prompt text or templates
--   - tool: Tool access grants or restrictions
--   - weight: Behavior weight modifications
--   - nats: NATS subject subscriptions
--   - model: Model preference overrides
--   - eval: Evaluation gate adjustments

-- Create persona_enhancements table
CREATE TABLE IF NOT EXISTS pmoves_core.persona_enhancements (
    enhancement_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    persona_id uuid NOT NULL REFERENCES pmoves_core.personas(persona_id) ON DELETE CASCADE,
    enhancement_type text NOT NULL
        CONSTRAINT persona_enhancement_type_check
        CHECK (enhancement_type IN ('prompt', 'tool', 'weight', 'nats', 'model', 'eval', 'geometry', 'voice')),
    enhancement_name text NOT NULL,
    enhancement_value jsonb NOT NULL,
    priority int DEFAULT 0,
    metadata jsonb DEFAULT '{}'::jsonb,
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now()
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_persona_enhancements_persona_id
    ON pmoves_core.persona_enhancements(persona_id);
CREATE INDEX IF NOT EXISTS idx_persona_enhancements_type
    ON pmoves_core.persona_enhancements(enhancement_type);
CREATE INDEX IF NOT EXISTS idx_persona_enhancements_priority
    ON pmoves_core.persona_enhancements(priority DESC);
CREATE INDEX IF NOT EXISTS idx_persona_enhancements_name
    ON pmoves_core.persona_enhancements(enhancement_name);

-- Unique constraint: one enhancement of given name per persona
CREATE UNIQUE INDEX IF NOT EXISTS uq_persona_enhancement_name
    ON pmoves_core.persona_enhancements(persona_id, enhancement_name);

-- Updated at trigger
CREATE OR REPLACE FUNCTION pmoves_core.update_persona_enhancement_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER persona_enhancement_updated_at
    BEFORE UPDATE ON pmoves_core.persona_enhancements
    FOR EACH ROW
    EXECUTE FUNCTION pmoves_core.update_persona_enhancement_updated_at();

-- Grant permissions
GRANT SELECT ON pmoves_core.persona_enhancements TO postgrest_anon, postgrest_auth_user;
GRANT INSERT, UPDATE, DELETE ON pmoves_core.persona_enhancements TO postgrest_auth_user;

-- Example enhancements for reference (commented out)
/*
-- Prompt enhancement: Add CHIT geometry awareness to a persona
INSERT INTO pmoves_core.persona_enhancements (persona_id, enhancement_type, enhancement_name, enhancement_value, priority)
SELECT p.persona_id, 'geometry', 'chit-awareness',
'{
  "enabled": true,
  "tools": ["geometry.jump", "geometry.decode_text"],
  "default_shape_id": "super_0",
  "decode_mode": "exact"
}'::jsonb, 10
FROM pmoves_core.personas p WHERE p.name = 'Archon';

-- Tool enhancement: Grant code review access
INSERT INTO pmoves_core.persona_enhancements (persona_id, enhancement_type, enhancement_name, enhancement_value, priority)
SELECT p.persona_id, 'tool', 'code-review-access',
'{
  "tools": ["git", "code-review", "testing"],
  "permissions": ["read", "write"],
  "scope": ["PMOVES.AI"]
}'::jsonb, 5
FROM pmoves_core.personas p WHERE p.name = 'Developer';

-- Weight enhancement: Adjust behavior weights for research-heavy persona
INSERT INTO pmoves_core.persona_enhancements (persona_id, enhancement_type, enhancement_name, enhancement_value, priority)
SELECT p.persona_id, 'weight', 'research-optimized',
'{
  "decode": 0.2,
  "retrieve": 0.6,
  "generate": 0.2
}'::jsonb, 8
FROM pmoves_core.personas p WHERE p.name = 'Researcher';
*/

COMMENT ON TABLE pmoves_core.persona_enhancements IS 'Modular enhancements for personas - supports dynamic configuration for Agent Zero/Archon agent creation';
COMMENT ON COLUMN pmoves_core.persona_enhancements.enhancement_type IS 'Type of enhancement: prompt, tool, weight, nats, model, eval, geometry, voice';
COMMENT ON COLUMN pmoves_core.persona_enhancements.enhancement_value IS 'JSONB value containing enhancement configuration';
COMMENT ON COLUMN pmoves_core.persona_enhancements.priority IS 'Higher priority enhancements are applied first';
