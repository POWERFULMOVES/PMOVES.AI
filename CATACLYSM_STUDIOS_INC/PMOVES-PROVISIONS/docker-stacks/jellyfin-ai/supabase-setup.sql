
-- Media table for storing Jellyfin media information
CREATE TABLE IF NOT EXISTS media (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    jellyfin_id TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    path TEXT,
    type TEXT,
    duration DECIMAL,
    size_bytes BIGINT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Media analysis table for AI-generated content
CREATE TABLE IF NOT EXISTS media_analysis (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    media_id UUID REFERENCES media(id) ON DELETE CASCADE,
    ai_description TEXT,
    ai_analysis JSONB,
    audio_features JSONB,
    processing_status TEXT DEFAULT 'pending',
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Content creation projects
CREATE TABLE IF NOT EXISTS content_projects (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    media_ids UUID[] DEFAULT '{}',
    project_type TEXT, -- 'youtube', 'podcast', 'mix', etc.
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- YouTube content tracking
CREATE TABLE IF NOT EXISTS youtube_content (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    project_id UUID REFERENCES content_projects(id) ON DELETE CASCADE,
    video_id TEXT,
    title TEXT,
    description TEXT,
    tags TEXT[],
    thumbnail_url TEXT,
    upload_status TEXT DEFAULT 'draft',
    analytics_data JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- User preferences and settings
CREATE TABLE IF NOT EXISTS user_settings (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID NOT NULL,
    settings JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Processing queue for async operations
CREATE TABLE IF NOT EXISTS processing_queue (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    operation_type TEXT NOT NULL,
    payload JSONB NOT NULL,
    status TEXT DEFAULT 'pending',
    priority INTEGER DEFAULT 0,
    retry_count INTEGER DEFAULT 0,
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_media_jellyfin_id ON media(jellyfin_id);
CREATE INDEX IF NOT EXISTS idx_media_type ON media(type);
CREATE INDEX IF NOT EXISTS idx_media_analysis_media_id ON media_analysis(media_id);
CREATE INDEX IF NOT EXISTS idx_media_analysis_status ON media_analysis(processing_status);
CREATE INDEX IF NOT EXISTS idx_content_projects_type ON content_projects(project_type);
CREATE INDEX IF NOT EXISTS idx_processing_queue_status ON processing_queue(status);
CREATE INDEX IF NOT EXISTS idx_processing_queue_priority ON processing_queue(priority DESC);

-- Update triggers
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_media_updated_at BEFORE UPDATE ON media
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_media_analysis_updated_at BEFORE UPDATE ON media_analysis
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_content_projects_updated_at BEFORE UPDATE ON content_projects
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_youtube_content_updated_at BEFORE UPDATE ON youtube_content
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_user_settings_updated_at BEFORE UPDATE ON user_settings
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_processing_queue_updated_at BEFORE UPDATE ON processing_queue
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Row Level Security (RLS) policies
ALTER TABLE media ENABLE ROW LEVEL SECURITY;
ALTER TABLE media_analysis ENABLE ROW LEVEL SECURITY;
ALTER TABLE content_projects ENABLE ROW LEVEL SECURITY;
ALTER TABLE youtube_content ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_settings ENABLE ROW LEVEL SECURITY;

-- Allow authenticated users to read all media
CREATE POLICY "Allow authenticated read access" ON media
    FOR SELECT TO authenticated USING (true);

-- Allow authenticated users to insert/update their own content
CREATE POLICY "Allow authenticated write access" ON media
    FOR ALL TO authenticated USING (true);

-- Apply similar policies to other tables
CREATE POLICY "Allow authenticated access" ON media_analysis
    FOR ALL TO authenticated USING (true);

CREATE POLICY "Allow authenticated access" ON content_projects
    FOR ALL TO authenticated USING (true);

CREATE POLICY "Allow authenticated access" ON youtube_content
    FOR ALL TO authenticated USING (true);

CREATE POLICY "Allow user settings access" ON user_settings
    FOR ALL TO authenticated USING (auth.uid() = user_id);
