-- Voice Persona & Voice Session Tables
-- Migration: 2025-12-10_voice_personas.sql
-- Purpose: Database schema for Flute Voice Gateway (ports 8055/8056)
-- Service: Multimodal voice communication layer with persona management

-- ============================================================================
-- Table: voice_persona
-- Purpose: Store voice persona configurations with provider-specific settings
-- Links to agents and persona avatars for multimodal representation
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.voice_persona (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    slug text NOT NULL UNIQUE,
    name text NOT NULL,
    agent_id uuid REFERENCES pmoves_core.agent(id),
    avatar_id bigint REFERENCES public.persona_avatar(id),

    -- Provider configuration
    voice_provider text NOT NULL DEFAULT 'vibevoice' CHECK (
        voice_provider IN ('vibevoice', 'ultimate_tts', 'whisper', 'elevenlabs', 'ollama')
    ),
    voice_model text,
    voice_sample_uri text,  -- MinIO: assets/voice-samples/{slug}.wav
    voice_config jsonb NOT NULL DEFAULT '{}'::jsonb,

    -- Personality and voice characteristics
    personality_traits text[] DEFAULT '{}',
    language text NOT NULL DEFAULT 'en',
    speaking_rate float DEFAULT 1.0 CHECK (speaking_rate > 0 AND speaking_rate <= 2.0),
    pitch_shift float DEFAULT 0.0 CHECK (pitch_shift >= -12.0 AND pitch_shift <= 12.0),

    -- Status
    is_active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

-- Index for fast lookups by slug (primary query pattern)
CREATE INDEX IF NOT EXISTS idx_voice_persona_slug
    ON public.voice_persona(slug);

-- Index for finding personas by agent
CREATE INDEX IF NOT EXISTS idx_voice_persona_agent
    ON public.voice_persona(agent_id) WHERE agent_id IS NOT NULL;

-- Index for filtering active personas
CREATE INDEX IF NOT EXISTS idx_voice_persona_active
    ON public.voice_persona(is_active) WHERE is_active = true;

-- Index for provider-specific queries
CREATE INDEX IF NOT EXISTS idx_voice_persona_provider
    ON public.voice_persona(voice_provider);

-- GIN index for personality traits array searches
CREATE INDEX IF NOT EXISTS idx_voice_persona_traits
    ON public.voice_persona USING GIN (personality_traits);

COMMENT ON TABLE public.voice_persona IS
    'Voice persona configurations for Flute multimodal communication layer';

COMMENT ON COLUMN public.voice_persona.voice_sample_uri IS
    'MinIO URI for voice sample: minio://assets/voice-samples/{slug}.wav';

COMMENT ON COLUMN public.voice_persona.voice_config IS
    'Provider-specific configuration (vibevoice: cfg/steps, ultimate_tts: speaker_id, elevenlabs: voice_id/stability)';

-- ============================================================================
-- Table: voice_session
-- Purpose: Track voice interaction sessions with state machine and metrics
-- Links to agents, Claude sessions, and voice personas
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.voice_session (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id uuid REFERENCES pmoves_core.agent(id),
    session_id uuid,  -- Links to claude_sessions or other session tables
    voice_persona_id uuid REFERENCES public.voice_persona(id),

    -- State machine
    state text NOT NULL DEFAULT 'idle' CHECK (state IN (
        'idle', 'listening', 'processing', 'speaking'
    )),

    -- Metrics
    total_tts_requests int DEFAULT 0,
    total_stt_requests int DEFAULT 0,
    total_audio_seconds float DEFAULT 0.0,

    -- Session lifecycle
    started_at timestamptz NOT NULL DEFAULT now(),
    ended_at timestamptz
);

-- Index for finding active sessions (not ended)
CREATE INDEX IF NOT EXISTS idx_voice_session_active
    ON public.voice_session(state) WHERE ended_at IS NULL;

-- Index for finding sessions by persona
CREATE INDEX IF NOT EXISTS idx_voice_session_persona
    ON public.voice_session(voice_persona_id) WHERE voice_persona_id IS NOT NULL;

-- Index for finding sessions by agent
CREATE INDEX IF NOT EXISTS idx_voice_session_agent
    ON public.voice_session(agent_id) WHERE agent_id IS NOT NULL;

-- Index for session duration analysis
CREATE INDEX IF NOT EXISTS idx_voice_session_started
    ON public.voice_session(started_at DESC);

COMMENT ON TABLE public.voice_session IS
    'Voice interaction sessions with state tracking and usage metrics';

COMMENT ON COLUMN public.voice_session.state IS
    'Session state machine: idle -> listening -> processing -> speaking -> idle';

COMMENT ON COLUMN public.voice_session.total_audio_seconds IS
    'Total audio duration (TTS + STT) in seconds';

-- ============================================================================
-- Trigger: Auto-update updated_at timestamp
-- ============================================================================

CREATE OR REPLACE FUNCTION update_voice_persona_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_voice_persona_updated ON public.voice_persona;
CREATE TRIGGER trg_voice_persona_updated
    BEFORE UPDATE ON public.voice_persona
    FOR EACH ROW EXECUTE FUNCTION update_voice_persona_updated_at();

-- ============================================================================
-- Row Level Security (RLS) Policies
-- ============================================================================

-- Enable RLS on both tables
ALTER TABLE public.voice_persona ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.voice_session ENABLE ROW LEVEL SECURITY;

-- Policy: service_role has full access
DROP POLICY IF EXISTS voice_persona_service_role ON public.voice_persona;
CREATE POLICY voice_persona_service_role
    ON public.voice_persona
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

DROP POLICY IF EXISTS voice_session_service_role ON public.voice_session;
CREATE POLICY voice_session_service_role
    ON public.voice_session
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Policy: authenticated users can read all personas
DROP POLICY IF EXISTS voice_persona_authenticated_select ON public.voice_persona;
CREATE POLICY voice_persona_authenticated_select
    ON public.voice_persona
    FOR SELECT
    TO authenticated
    USING (true);

-- Policy: authenticated users can read all sessions
DROP POLICY IF EXISTS voice_session_authenticated_select ON public.voice_session;
CREATE POLICY voice_session_authenticated_select
    ON public.voice_session
    FOR SELECT
    TO authenticated
    USING (true);

-- ============================================================================
-- Realtime: Enable for live subscriptions
-- ============================================================================

-- Enable realtime for voice_session table (state changes, metrics updates)
ALTER PUBLICATION supabase_realtime ADD TABLE public.voice_session;

-- ============================================================================
-- Views: Convenient queries
-- ============================================================================

-- View: Active voice sessions with persona details
CREATE OR REPLACE VIEW public.voice_sessions_active AS
SELECT
    vs.id,
    vs.agent_id,
    vs.session_id,
    vs.state,
    vs.total_tts_requests,
    vs.total_stt_requests,
    vs.total_audio_seconds,
    vs.started_at,
    (NOW() - vs.started_at) as session_duration,
    vp.slug as persona_slug,
    vp.name as persona_name,
    vp.voice_provider
FROM public.voice_session vs
LEFT JOIN public.voice_persona vp ON vs.voice_persona_id = vp.id
WHERE vs.ended_at IS NULL
ORDER BY vs.started_at DESC;

COMMENT ON VIEW public.voice_sessions_active IS
    'Currently active voice sessions with persona information';

-- View: Voice persona usage statistics
CREATE OR REPLACE VIEW public.voice_persona_stats AS
SELECT
    vp.id,
    vp.slug,
    vp.name,
    vp.voice_provider,
    COUNT(vs.id) as total_sessions,
    COALESCE(SUM(vs.total_tts_requests), 0) as total_tts_requests,
    COALESCE(SUM(vs.total_stt_requests), 0) as total_stt_requests,
    COALESCE(SUM(vs.total_audio_seconds), 0) as total_audio_seconds,
    COALESCE(AVG(vs.total_audio_seconds), 0) as avg_audio_seconds_per_session
FROM public.voice_persona vp
LEFT JOIN public.voice_session vs ON vp.id = vs.voice_persona_id
WHERE vp.is_active = true
GROUP BY vp.id, vp.slug, vp.name, vp.voice_provider
ORDER BY total_sessions DESC;

COMMENT ON VIEW public.voice_persona_stats IS
    'Voice persona usage statistics across all sessions';

-- ============================================================================
-- Functions: Voice session management
-- ============================================================================

-- Function: Get active session for an agent
CREATE OR REPLACE FUNCTION get_active_voice_session(p_agent_id uuid)
RETURNS uuid AS $$
BEGIN
    RETURN (
        SELECT id
        FROM public.voice_session
        WHERE agent_id = p_agent_id
          AND ended_at IS NULL
        ORDER BY started_at DESC
        LIMIT 1
    );
END;
$$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION get_active_voice_session IS
    'Get the most recent active voice session for an agent';

-- Function: End a voice session
CREATE OR REPLACE FUNCTION end_voice_session(p_session_id uuid)
RETURNS boolean AS $$
BEGIN
    UPDATE public.voice_session
    SET ended_at = NOW(),
        state = 'idle'
    WHERE id = p_session_id
      AND ended_at IS NULL;

    RETURN FOUND;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION end_voice_session IS
    'Mark a voice session as ended';

-- ============================================================================
-- Seed Data: Default voice personas
-- ============================================================================

INSERT INTO public.voice_persona (slug, name, voice_provider, personality_traits, language) VALUES
    ('agent-zero-default', 'Agent Zero', 'vibevoice', ARRAY['professional', 'helpful', 'authoritative'], 'en'),
    ('archon-librarian', 'Archon Librarian', 'vibevoice', ARRAY['calm', 'authoritative', 'knowledgeable'], 'en'),
    ('creative-artist', 'Creative Artist', 'vibevoice', ARRAY['enthusiastic', 'expressive', 'imaginative'], 'en')
ON CONFLICT (slug) DO NOTHING;
