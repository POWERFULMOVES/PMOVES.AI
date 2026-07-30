-- v5.22: YouTube playlist video metadata table
-- Stores crawled video metadata from YouTube Data API v3 for the DARKXSIDE
-- playlist and future playlists. Populated by pmoves/tools/yt_playlist_crawl.py.

SET search_path TO pmoves_core;

CREATE TABLE IF NOT EXISTS youtube_videos (
    video_id TEXT PRIMARY KEY,
    playlist_id TEXT,
    playlist_position INTEGER,
    title TEXT,
    description TEXT,
    channel_id TEXT,
    channel_title TEXT,
    published_at TIMESTAMPTZ,
    duration_seconds INTEGER,
    view_count BIGINT,
    like_count BIGINT,
    comment_count BIGINT,
    tags TEXT[],
    category_id TEXT,
    thumbnail_default TEXT,
    thumbnail_medium TEXT,
    thumbnail_high TEXT,
    downloaded BOOLEAN DEFAULT FALSE,
    transcribed BOOLEAN DEFAULT FALSE,
    ingested BOOLEAN DEFAULT FALSE,
    crawl_batch TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE youtube_videos ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS youtube_videos_service_role ON youtube_videos;
CREATE POLICY youtube_videos_service_role ON youtube_videos
    FOR ALL USING (auth.role() = 'service_role');

GRANT SELECT, INSERT, UPDATE, DELETE ON youtube_videos TO anon, authenticated, service_role;

CREATE INDEX IF NOT EXISTS idx_yv_playlist ON youtube_videos(playlist_id);
CREATE INDEX IF NOT EXISTS idx_yv_not_downloaded ON youtube_videos(downloaded) WHERE downloaded = FALSE;
CREATE INDEX IF NOT EXISTS idx_yv_published ON youtube_videos(published_at DESC);

ALTER TABLE youtube_videos REPLICA IDENTITY FULL;
