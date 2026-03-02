-- Migration: Persona-Model Resolution View
-- Date: 2026-03-01
-- Purpose: Runtime view joining persona → model → provider for grounded agent identity resolution
--
-- Personas reference models by name string (model_preference), but there's no
-- SQL view that resolves persona→model→provider in a single query. This view
-- enables runtime resolution of which provider/API endpoint to call for each persona.

-- =============================================================================
-- Resolution View
-- =============================================================================

CREATE OR REPLACE VIEW pmoves_core.persona_model_resolution
WITH (security_invoker = true) AS
SELECT
    p.persona_id,
    p.name           AS persona_name,
    p.version        AS persona_version,
    p.thread_type,
    p.model_preference,
    p.temperature,
    p.max_tokens,
    p.is_active      AS persona_active,
    m.id             AS model_id,
    m.name           AS model_name,
    m.model_id       AS model_identifier,
    m.model_type,
    m.provider_id,
    mp.name          AS provider_name,
    mp.type          AS provider_type,
    mp.api_base,
    mp.api_key_env_var,
    m.context_length,
    m.capabilities,
    m.vram_mb
FROM pmoves_core.personas p
LEFT JOIN pmoves_core.models m
    ON m.model_id = p.model_preference
LEFT JOIN pmoves_core.model_providers mp
    ON mp.id = m.provider_id;

COMMENT ON VIEW pmoves_core.persona_model_resolution IS
    'Runtime resolution view: persona → model → provider. '
    'Joins persona model_preference string to models.model_id and their providers. '
    'Used by Agent Zero and Archon to resolve which API endpoint to call for each persona.';

-- =============================================================================
-- RLS Policy (service_role read access)
-- =============================================================================
-- Views inherit RLS from base tables; grant explicit SELECT to service roles

GRANT SELECT ON pmoves_core.persona_model_resolution TO postgrest_anon, postgrest_auth_user;

-- =============================================================================
-- Convenience: Active persona summary for quick lookup
-- =============================================================================

CREATE OR REPLACE VIEW pmoves_core.active_persona_summary
WITH (security_invoker = true) AS
SELECT
    p.persona_id,
    p.name           AS persona_name,
    p.thread_type,
    p.model_preference,
    p.temperature,
    p.behavior_weights,
    mp.name          AS provider_name,
    mp.api_base,
    m.context_length,
    m.capabilities
FROM pmoves_core.personas p
LEFT JOIN pmoves_core.models m
    ON m.model_id = p.model_preference
LEFT JOIN pmoves_core.model_providers mp
    ON mp.id = m.provider_id
WHERE p.is_active = true;

COMMENT ON VIEW pmoves_core.active_persona_summary IS
    'Quick-lookup view of active personas with resolved model/provider info.';

GRANT SELECT ON pmoves_core.active_persona_summary TO postgrest_anon, postgrest_auth_user;
