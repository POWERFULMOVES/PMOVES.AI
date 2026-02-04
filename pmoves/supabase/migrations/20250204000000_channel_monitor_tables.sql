-- PMOVES Channel Monitor - User Sources and Tokens Tables
-- Enables dynamic YouTube channel monitoring with OAuth integration
-- Required by: pmoves-channel-monitor service

-- Enable UUID extension if not already enabled
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ==============================================================================
-- USER TOKENS TABLE
-- Stores OAuth refresh tokens for YouTube API access
-- ==============================================================================
CREATE TABLE IF NOT EXISTS pmoves.user_tokens (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL,
    provider TEXT NOT NULL DEFAULT 'youtube',
    scope TEXT,
    refresh_token TEXT NOT NULL,
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for user_tokens
CREATE INDEX IF NOT EXISTS idx_user_tokens_user_id ON pmoves.user_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_user_tokens_provider ON pmoves.user_tokens(provider);

-- ==============================================================================
-- USER SOURCES TABLE
-- Stores user-configured YouTube channels and playlists for monitoring
-- ==============================================================================
CREATE TABLE IF NOT EXISTS pmoves.user_sources (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL,
    provider TEXT NOT NULL DEFAULT 'youtube',
    source_type TEXT NOT NULL, -- 'channel', 'playlist', 'video'
    source_identifier TEXT,
    source_url TEXT,
    namespace TEXT NOT NULL DEFAULT 'pmoves',
    tags JSONB DEFAULT '[]'::jsonb,
    status TEXT NOT NULL DEFAULT 'active', -- 'active', 'paused', 'disabled'
    auto_process BOOLEAN NOT NULL DEFAULT true,
    check_interval_minutes INT NOT NULL DEFAULT 60,
    filters JSONB DEFAULT '{}'::jsonb,
    yt_options JSONB DEFAULT '{}'::jsonb,
    token_id UUID REFERENCES pmoves.user_tokens(id) ON DELETE SET NULL,
    last_check_at TIMESTAMPTZ,
    last_ingest_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, provider, COALESCE(source_identifier, ''), COALESCE(source_url, ''))
);

-- Indexes for user_sources
CREATE INDEX IF NOT EXISTS idx_user_sources_user_id ON pmoves.user_sources(user_id);
CREATE INDEX IF NOT EXISTS idx_user_sources_status ON pmoves.user_sources(status);
CREATE INDEX IF NOT EXISTS idx_user_sources_namespace ON pmoves.user_sources(namespace);
CREATE INDEX IF NOT EXISTS idx_user_sources_token_id ON pmoves.user_sources(token_id);
CREATE INDEX IF NOT EXISTS idx_user_sources_source_type ON pmoves.user_sources(source_type);

-- Full-text search on source_identifier
CREATE INDEX IF NOT EXISTS idx_user_sources_search ON pmoves.user_sources USING gin(to_tsvector('english', COALESCE(source_identifier, '')));

-- ==============================================================================
-- CHANNEL MONITORING TABLE
-- Internal tracking table for channel monitoring state
-- Note: This is created by the channel-monitor service itself
-- ==============================================================================
CREATE TABLE IF NOT EXISTS pmoves.channel_monitoring (
    id TEXT PRIMARY KEY,
    channel_id TEXT,
    last_check TIMESTAMPTZ,
    last_video_id TEXT,
    last_video_timestamp TIMESTAMPTZ,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_channel_monitoring_channel_id ON pmoves.channel_monitoring(channel_id);

-- ==============================================================================
-- ROW LEVEL SECURITY (RLS)
-- ==============================================================================

-- Enable RLS on all tables
ALTER TABLE pmoves.user_tokens ENABLE ROW LEVEL SECURITY;
ALTER TABLE pmoves.user_sources ENABLE ROW LEVEL SECURITY;
ALTER TABLE pmoves.channel_monitoring ENABLE ROW LEVEL SECURITY;

-- RLS Policies for user_tokens
CREATE POLICY "Users can view their own tokens"
    ON pmoves.user_tokens FOR SELECT
    USING (auth.uid()::text = user_id::text);

CREATE POLICY "Users can insert their own tokens"
    ON pmoves.user_tokens FOR INSERT
    WITH CHECK (auth.uid()::text = user_id::text);

CREATE POLICY "Users can update their own tokens"
    ON pmoves.user_tokens FOR UPDATE
    USING (auth.uid()::text = user_id::text);

CREATE POLICY "Service role can manage all tokens"
    ON pmoves.user_tokens FOR ALL
    USING (jwt_claim_role() = 'service_role');

-- RLS Policies for user_sources
CREATE POLICY "Users can view their own sources"
    ON pmoves.user_sources FOR SELECT
    USING (auth.uid()::text = user_id::text);

CREATE POLICY "Users can insert their own sources"
    ON pmoves.user_sources FOR INSERT
    WITH CHECK (auth.uid()::text = user_id::text);

CREATE POLICY "Users can update their own sources"
    ON pmoves.user_sources FOR UPDATE
    USING (auth.uid()::text = user_id::text);

CREATE POLICY "Users can delete their own sources"
    ON pmoves.user_sources FOR DELETE
    USING (auth.uid()::text = user_id::text);

CREATE POLICY "Service role can manage all sources"
    ON pmoves.user_sources FOR ALL
    USING (jwt_claim_role() = 'service_role');

-- RLS Policies for channel_monitoring
CREATE POLICY "Service role full access to monitoring"
    ON pmoves.channel_monitoring FOR ALL
    USING (jwt_claim_role() = 'service_role');

-- ==============================================================================
-- FUNCTIONS AND TRIGGERS
-- ==============================================================================

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION pmoves.update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Triggers for updated_at
CREATE TRIGGER update_user_tokens_updated_at
    BEFORE UPDATE ON pmoves.user_tokens
    FOR EACH ROW
    EXECUTE FUNCTION pmoves.update_updated_at();

CREATE TRIGGER update_user_sources_updated_at
    BEFORE UPDATE ON pmoves.user_sources
    FOR EACH ROW
    EXECUTE FUNCTION pmoves.update_updated_at();

CREATE TRIGGER update_channel_monitoring_updated_at
    BEFORE UPDATE ON pmoves.channel_monitoring
    FOR EACH ROW
    EXECUTE FUNCTION pmoves.update_updated_at();

-- ==============================================================================
-- GRANTS
-- ==============================================================================

-- Grant access to authenticated users
GRANT USAGE ON SCHEMA pmoves TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON pmoves.user_tokens TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON pmoves.user_sources TO authenticated;
GRANT SELECT ON pmoves.channel_monitoring TO authenticated;

-- Grant access to service role
GRANT USAGE ON SCHEMA pmoves TO service_role;
GRANT ALL PRIVILEGES ON pmoves.user_tokens TO service_role;
GRANT ALL PRIVILEGES ON pmoves.user_sources TO service_role;
GRANT ALL PRIVILEGES ON pmoves.channel_monitoring TO service_role;

-- Grant access to anon (read-only for public sources if needed)
GRANT USAGE ON SCHEMA pmoves TO anon;
GRANT SELECT ON pmoves.channel_monitoring TO anon;

-- ==============================================================================
-- COMMENTS
-- ==============================================================================
COMMENT ON TABLE pmoves.user_tokens IS 'Stores OAuth refresh tokens for YouTube API access';
COMMENT ON TABLE pmoves.user_sources IS 'Stores user-configured YouTube channels and playlists for monitoring';
COMMENT ON TABLE pmoves.channel_monitoring IS 'Internal tracking table for channel monitoring state';
