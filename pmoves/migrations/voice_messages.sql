-- Voice Messages Schema for Multi-Platform Voice Agents
-- Supports Discord, Telegram, WhatsApp voice interactions

-- Main voice messages table
CREATE TABLE IF NOT EXISTS voice_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Platform identification
    platform VARCHAR(20) NOT NULL CHECK (platform IN ('discord', 'telegram', 'whatsapp')),
    platform_message_id VARCHAR(255),  -- Original message ID from platform

    -- User identification
    user_id VARCHAR(255) NOT NULL,
    user_name VARCHAR(255),
    session_id VARCHAR(255),  -- For conversation continuity

    -- Audio data
    audio_url TEXT,  -- MinIO or platform URL
    audio_duration_seconds FLOAT,
    audio_format VARCHAR(20),  -- wav, mp3, ogg, etc.

    -- Transcription
    transcript TEXT,
    transcript_language VARCHAR(10),
    transcript_confidence FLOAT,

    -- AI Response
    response_text TEXT,
    response_audio_url TEXT,  -- TTS generated audio
    model_used VARCHAR(100),  -- e.g., "claude-sonnet-4-5", "gpt-4o-mini"

    -- RAG/Knowledge
    knowledge_sources JSONB,  -- Hi-RAG sources used

    -- Metadata
    metadata JSONB DEFAULT '{}',

    -- Timing
    created_at TIMESTAMPTZ DEFAULT NOW(),
    transcribed_at TIMESTAMPTZ,
    responded_at TIMESTAMPTZ,

    -- Processing status
    status VARCHAR(20) DEFAULT 'received' CHECK (status IN ('received', 'transcribing', 'processing', 'responding', 'completed', 'failed')),
    error_message TEXT
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_voice_messages_platform ON voice_messages(platform);
CREATE INDEX IF NOT EXISTS idx_voice_messages_user_id ON voice_messages(user_id);
CREATE INDEX IF NOT EXISTS idx_voice_messages_session_id ON voice_messages(session_id);
CREATE INDEX IF NOT EXISTS idx_voice_messages_created_at ON voice_messages(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_voice_messages_status ON voice_messages(status);

-- Voice sessions for conversation memory
CREATE TABLE IF NOT EXISTS voice_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Platform & User
    platform VARCHAR(20) NOT NULL,
    user_id VARCHAR(255) NOT NULL,

    -- Session metadata
    started_at TIMESTAMPTZ DEFAULT NOW(),
    last_activity_at TIMESTAMPTZ DEFAULT NOW(),
    message_count INTEGER DEFAULT 0,

    -- Conversation context (for AI memory)
    context_summary TEXT,  -- Rolling summary of conversation

    -- Configuration
    voice_enabled BOOLEAN DEFAULT true,  -- Whether to respond with voice
    preferred_language VARCHAR(10) DEFAULT 'en',

    -- Status
    is_active BOOLEAN DEFAULT true,

    UNIQUE(platform, user_id)
);

CREATE INDEX IF NOT EXISTS idx_voice_sessions_platform_user ON voice_sessions(platform, user_id);
CREATE INDEX IF NOT EXISTS idx_voice_sessions_active ON voice_sessions(is_active) WHERE is_active = true;

-- Voice personas (optional - for different AI personalities)
CREATE TABLE IF NOT EXISTS voice_personas (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    slug VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    description TEXT,

    -- Voice configuration
    tts_provider VARCHAR(50) DEFAULT 'elevenlabs',  -- elevenlabs, openai, local
    tts_voice_id VARCHAR(100),  -- Provider-specific voice ID
    tts_settings JSONB DEFAULT '{}',  -- speed, pitch, etc.

    -- AI configuration
    system_prompt TEXT,
    model_override VARCHAR(100),  -- Override default model

    -- Status
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Default persona
INSERT INTO voice_personas (slug, name, description, tts_provider, system_prompt, is_active)
VALUES (
    'default',
    'PMOVES Assistant',
    'Default voice assistant persona',
    'elevenlabs',
    'You are a helpful voice assistant for PMOVES.AI. Keep responses concise and conversational, suitable for voice output. Aim for 1-3 sentences unless more detail is specifically requested.',
    true
) ON CONFLICT (slug) DO NOTHING;

-- Function to update session last activity
CREATE OR REPLACE FUNCTION update_voice_session_activity()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE voice_sessions
    SET
        last_activity_at = NOW(),
        message_count = message_count + 1
    WHERE platform = NEW.platform AND user_id = NEW.user_id;

    -- Create session if doesn't exist
    IF NOT FOUND THEN
        INSERT INTO voice_sessions (platform, user_id)
        VALUES (NEW.platform, NEW.user_id);
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to auto-update session on new message
DROP TRIGGER IF EXISTS trg_voice_message_session ON voice_messages;
CREATE TRIGGER trg_voice_message_session
    AFTER INSERT ON voice_messages
    FOR EACH ROW
    EXECUTE FUNCTION update_voice_session_activity();

-- Grant permissions (adjust role name as needed)
-- GRANT ALL ON voice_messages TO pmoves_service;
-- GRANT ALL ON voice_sessions TO pmoves_service;
-- GRANT ALL ON voice_personas TO pmoves_service;

COMMENT ON TABLE voice_messages IS 'Stores all voice interactions across Discord, Telegram, and WhatsApp';
COMMENT ON TABLE voice_sessions IS 'Tracks conversation sessions per user per platform';
COMMENT ON TABLE voice_personas IS 'Configurable AI voice personas with different voices and prompts';

-- Enable Row Level Security
ALTER TABLE voice_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE voice_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE voice_personas ENABLE ROW LEVEL SECURITY;

-- Grant permissions to anon role for development
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE voice_messages TO anon;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE voice_sessions TO anon;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE voice_personas TO anon;

-- RLS Policies for voice_messages
DO $$
BEGIN
  CREATE POLICY voice_messages_anon_all
    ON voice_messages
    FOR ALL
    TO anon
    USING (true)
    WITH CHECK (true);
EXCEPTION
  WHEN duplicate_object THEN NULL;
END;
$$;

-- RLS Policies for voice_sessions
DO $$
BEGIN
  CREATE POLICY voice_sessions_anon_all
    ON voice_sessions
    FOR ALL
    TO anon
    USING (true)
    WITH CHECK (true);
EXCEPTION
  WHEN duplicate_object THEN NULL;
END;
$$;

-- RLS Policies for voice_personas
DO $$
BEGIN
  CREATE POLICY voice_personas_anon_all
    ON voice_personas
    FOR ALL
    TO anon
    USING (true)
    WITH CHECK (true);
EXCEPTION
  WHEN duplicate_object THEN NULL;
END;
$$;
