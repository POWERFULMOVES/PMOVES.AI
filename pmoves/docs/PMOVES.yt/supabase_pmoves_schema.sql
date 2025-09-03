-- PMOVES.AI YouTube RAG Database Schema
-- Complete Supabase setup with pgvector, TimescaleDB, and CoCa embeddings

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

-- Create schema for better organization
CREATE SCHEMA IF NOT EXISTS pmoves;

-- Set default search path
SET search_path TO pmoves, public;

-- ============================================
-- MAIN TABLES
-- ============================================

-- YouTube Videos Metadata Table
CREATE TABLE IF NOT EXISTS pmoves.youtube_videos (
    video_id VARCHAR(20) PRIMARY KEY,
    watch_url TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    uploader VARCHAR(255),
    channel_id VARCHAR(50),
    duration_seconds INTEGER,
    view_count BIGINT,
    like_count INTEGER,
    upload_date DATE,
    thumbnail_default TEXT,
    thumbnail_medium TEXT,
    thumbnail_high TEXT,
    thumbnail_maxres TEXT,
    tags TEXT[],
    categories TEXT[],
    language VARCHAR(10) DEFAULT 'en',
    has_captions BOOLEAN DEFAULT false,
    processed_status VARCHAR(20) DEFAULT 'pending',
    processed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    metadata JSONB DEFAULT '{}',
    
    -- Indexes
    CONSTRAINT youtube_videos_status_check 
        CHECK (processed_status IN ('pending', 'processing', 'completed', 'failed'))
);

-- YouTube Transcript Segments Table with CoCa embeddings
CREATE TABLE IF NOT EXISTS pmoves.youtube_segments (
    id BIGSERIAL PRIMARY KEY,
    video_id VARCHAR(20) NOT NULL REFERENCES pmoves.youtube_videos(video_id) ON DELETE CASCADE,
    segment_id INTEGER NOT NULL,
    text TEXT NOT NULL,
    start_seconds NUMERIC(10,3) NOT NULL,
    end_seconds NUMERIC(10,3) NOT NULL,
    start_timestamp VARCHAR(20),
    end_timestamp VARCHAR(20),
    timestamped_url TEXT,
    
    -- CoCa Multi-level Embeddings (3584 dimensions for Hugging Face)
    text_embedding vector(3584),
    context_embedding vector(3584),
    contrastive_embedding vector(3584),
    combined_embedding vector(3584),
    
    -- Embedding metadata
    embedding_model VARCHAR(100),
    embedding_version VARCHAR(20),
    embedding_generated_at TIMESTAMP WITH TIME ZONE,
    coca_window_size INTEGER DEFAULT 3,
    
    -- Search optimization fields
    text_tsv tsvector GENERATED ALWAYS AS (to_tsvector('english', text)) STORED,
    word_count INTEGER GENERATED ALWAYS AS (array_length(string_to_array(text, ' '), 1)) STORED,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Unique constraint
    CONSTRAINT unique_video_segment UNIQUE(video_id, segment_id)
);

-- YouTube Summaries Table (chunk-level aggregations)
CREATE TABLE IF NOT EXISTS pmoves.youtube_summaries (
    id BIGSERIAL PRIMARY KEY,
    video_id VARCHAR(20) NOT NULL REFERENCES pmoves.youtube_videos(video_id) ON DELETE CASCADE,
    chunk_id INTEGER NOT NULL,
    summary_text TEXT NOT NULL,
    segment_ids INTEGER[] NOT NULL,
    start_seconds NUMERIC(10,3) NOT NULL,
    end_seconds NUMERIC(10,3) NOT NULL,
    
    -- Summary embeddings
    summary_embedding vector(3584),
    
    -- Metadata
    summary_type VARCHAR(50) DEFAULT 'auto_generated',
    confidence_score NUMERIC(3,2),
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    CONSTRAINT unique_video_chunk UNIQUE(video_id, chunk_id)
);

-- Processing Queue Table
CREATE TABLE IF NOT EXISTS pmoves.processing_queue (
    id BIGSERIAL PRIMARY KEY,
    video_url TEXT NOT NULL,
    video_id VARCHAR(20),
    priority INTEGER DEFAULT 0,
    status VARCHAR(20) DEFAULT 'pending',
    attempts INTEGER DEFAULT 0,
    max_attempts INTEGER DEFAULT 3,
    error_message TEXT,
    metadata JSONB DEFAULT '{}',
    
    queued_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    failed_at TIMESTAMP WITH TIME ZONE,
    
    CONSTRAINT queue_status_check 
        CHECK (status IN ('pending', 'processing', 'completed', 'failed', 'cancelled'))
);

-- Search History Table (for learning and optimization)
CREATE TABLE IF NOT EXISTS pmoves.search_history (
    id BIGSERIAL PRIMARY KEY,
    query_text TEXT NOT NULL,
    query_embedding vector(3584),
    search_type VARCHAR(50) DEFAULT 'hybrid',
    results_count INTEGER,
    click_through_rate NUMERIC(3,2),
    user_session_id VARCHAR(100),
    response_time_ms INTEGER,
    
    searched_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================
-- INDEXES FOR PERFORMANCE
-- ============================================

-- Vector indexes using IVFFlat for similarity search
CREATE INDEX IF NOT EXISTS idx_segments_text_embedding 
    ON pmoves.youtube_segments USING ivfflat (text_embedding vector_cosine_ops)
    WITH (lists = 100);

CREATE INDEX IF NOT EXISTS idx_segments_context_embedding 
    ON pmoves.youtube_segments USING ivfflat (context_embedding vector_cosine_ops)
    WITH (lists = 100);

CREATE INDEX IF NOT EXISTS idx_segments_contrastive_embedding 
    ON pmoves.youtube_segments USING ivfflat (contrastive_embedding vector_cosine_ops)
    WITH (lists = 100);

CREATE INDEX IF NOT EXISTS idx_segments_combined_embedding 
    ON pmoves.youtube_segments USING ivfflat (combined_embedding vector_cosine_ops)
    WITH (lists = 100);

CREATE INDEX IF NOT EXISTS idx_summaries_embedding 
    ON pmoves.youtube_summaries USING ivfflat (summary_embedding vector_cosine_ops)
    WITH (lists = 50);

-- Full-text search indexes
CREATE INDEX IF NOT EXISTS idx_segments_text_gin 
    ON pmoves.youtube_segments USING gin(text_tsv);

CREATE INDEX IF NOT EXISTS idx_segments_text_trgm 
    ON pmoves.youtube_segments USING gin(text gin_trgm_ops);

-- B-tree indexes for filtering
CREATE INDEX IF NOT EXISTS idx_segments_video_id 
    ON pmoves.youtube_segments(video_id);

CREATE INDEX IF NOT EXISTS idx_segments_timestamps 
    ON pmoves.youtube_segments(start_seconds, end_seconds);

CREATE INDEX IF NOT EXISTS idx_videos_processed 
    ON pmoves.youtube_videos(processed_status, created_at);

CREATE INDEX IF NOT EXISTS idx_queue_status 
    ON pmoves.processing_queue(status, priority DESC, queued_at);

-- ============================================
-- TIMESCALEDB HYPERTABLES
-- ============================================

-- Convert search history to hypertable for time-series analysis
SELECT create_hypertable(
    'pmoves.search_history', 
    'searched_at',
    chunk_time_interval => INTERVAL '1 week',
    if_not_exists => TRUE
);

-- ============================================
-- FUNCTIONS AND STORED PROCEDURES
-- ============================================

-- CoCa-enhanced hybrid search function
CREATE OR REPLACE FUNCTION pmoves.coca_hybrid_search(
    query_embedding vector(3584),
    query_text TEXT,
    search_type TEXT DEFAULT 'hybrid',
    limit_results INTEGER DEFAULT 10
)
RETURNS TABLE (
    video_id VARCHAR,
    segment_id INTEGER,
    text TEXT,
    timestamped_url TEXT,
    start_seconds NUMERIC,
    end_seconds NUMERIC,
    coca_score NUMERIC,
    keyword_score NUMERIC,
    final_score NUMERIC
) 
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    WITH coca_search AS (
        -- Multi-level vector search with CoCa embeddings
        SELECT 
            s.video_id,
            s.segment_id,
            s.text,
            s.timestamped_url,
            s.start_seconds,
            s.end_seconds,
            (1 - (s.text_embedding <=> query_embedding)) * 0.5 +
            (1 - (s.context_embedding <=> query_embedding)) * 0.3 +
            (1 - (s.contrastive_embedding <=> query_embedding)) * 0.2 as coca_similarity
        FROM pmoves.youtube_segments s
        WHERE s.text_embedding IS NOT NULL
    ),
    keyword_search AS (
        -- Full-text search with ranking
        SELECT 
            s.video_id,
            s.segment_id,
            ts_rank_cd(s.text_tsv, plainto_tsquery('english', query_text)) as text_rank,
            similarity(s.text, query_text) as trigram_similarity
        FROM pmoves.youtube_segments s
        WHERE s.text_tsv @@ plainto_tsquery('english', query_text)
           OR s.text % query_text
    ),
    temporal_context AS (
        -- Boost segments with temporal context
        SELECT 
            s1.video_id,
            s1.segment_id,
            COUNT(DISTINCT s2.segment_id) * 0.01 as context_boost
        FROM pmoves.youtube_segments s1
        JOIN pmoves.youtube_segments s2 
            ON s1.video_id = s2.video_id
            AND ABS(s1.segment_id - s2.segment_id) <= 2
        GROUP BY s1.video_id, s1.segment_id
    )
    SELECT 
        cs.video_id,
        cs.segment_id,
        cs.text,
        cs.timestamped_url,
        cs.start_seconds,
        cs.end_seconds,
        cs.coca_similarity::NUMERIC as coca_score,
        COALESCE(GREATEST(ks.text_rank, ks.trigram_similarity), 0)::NUMERIC as keyword_score,
        (
            CASE 
                WHEN search_type = 'vector' THEN cs.coca_similarity
                WHEN search_type = 'keyword' THEN COALESCE(GREATEST(ks.text_rank, ks.trigram_similarity), 0)
                ELSE -- hybrid
                    cs.coca_similarity * 0.7 +
                    COALESCE(GREATEST(ks.text_rank, ks.trigram_similarity), 0) * 0.3 +
                    COALESCE(tc.context_boost, 0)
            END
        )::NUMERIC as final_score
    FROM coca_search cs
    LEFT JOIN keyword_search ks USING (video_id, segment_id)
    LEFT JOIN temporal_context tc USING (video_id, segment_id)
    WHERE cs.coca_similarity > 0.3 OR ks.text_rank > 0.1
    ORDER BY final_score DESC
    LIMIT limit_results;
END;
$$;

-- Function to get video context around a segment
CREATE OR REPLACE FUNCTION pmoves.get_segment_context(
    p_video_id VARCHAR,
    p_segment_id INTEGER,
    context_size INTEGER DEFAULT 2
)
RETURNS TABLE (
    segment_id INTEGER,
    text TEXT,
    start_seconds NUMERIC,
    end_seconds NUMERIC,
    is_target BOOLEAN
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT 
        s.segment_id,
        s.text,
        s.start_seconds,
        s.end_seconds,
        (s.segment_id = p_segment_id) as is_target
    FROM pmoves.youtube_segments s
    WHERE s.video_id = p_video_id
      AND s.segment_id BETWEEN (p_segment_id - context_size) AND (p_segment_id + context_size)
    ORDER BY s.segment_id;
END;
$$;

-- Update trigger for updated_at
CREATE OR REPLACE FUNCTION pmoves.update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_videos_updated_at
    BEFORE UPDATE ON pmoves.youtube_videos
    FOR EACH ROW
    EXECUTE FUNCTION pmoves.update_updated_at();

-- ============================================
-- VIEWS FOR COMMON QUERIES
-- ============================================

-- Overview of processing status
CREATE OR REPLACE VIEW pmoves.processing_overview AS
SELECT 
    processed_status,
    COUNT(*) as count,
    AVG(EXTRACT(EPOCH FROM (processed_at - created_at))/60)::INTEGER as avg_processing_minutes,
    MAX(created_at) as latest_addition
FROM pmoves.youtube_videos
GROUP BY processed_status;

-- Search performance metrics
CREATE OR REPLACE VIEW pmoves.search_metrics AS
SELECT 
    DATE_TRUNC('hour', searched_at) as hour,
    COUNT(*) as searches,
    AVG(response_time_ms) as avg_response_ms,
    AVG(results_count) as avg_results,
    AVG(click_through_rate) as avg_ctr
FROM pmoves.search_history
WHERE searched_at > NOW() - INTERVAL '7 days'
GROUP BY DATE_TRUNC('hour', searched_at)
ORDER BY hour DESC;

-- ============================================
-- ROW LEVEL SECURITY (RLS)
-- ============================================

-- Enable RLS for multi-tenant scenarios
ALTER TABLE pmoves.youtube_videos ENABLE ROW LEVEL SECURITY;
ALTER TABLE pmoves.youtube_segments ENABLE ROW LEVEL SECURITY;

-- Create policies (adjust based on your auth setup)
CREATE POLICY "Enable read access for all authenticated users" 
    ON pmoves.youtube_videos FOR SELECT 
    USING (true);

CREATE POLICY "Enable read access for all authenticated users" 
    ON pmoves.youtube_segments FOR SELECT 
    USING (true);

-- ============================================
-- INITIAL DATA AND PERMISSIONS
-- ============================================

-- Grant permissions to your application user
GRANT USAGE ON SCHEMA pmoves TO authenticated;
GRANT ALL ON ALL TABLES IN SCHEMA pmoves TO authenticated;
GRANT ALL ON ALL SEQUENCES IN SCHEMA pmoves TO authenticated;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA pmoves TO authenticated;

-- Create indexes concurrently for production (won't lock tables)
-- Run these separately if tables already have data:
-- CREATE INDEX CONCURRENTLY ...

-- ============================================
-- MAINTENANCE QUERIES
-- ============================================

-- Vacuum and analyze for optimal performance
-- Schedule these regularly
-- VACUUM ANALYZE pmoves.youtube_segments;
-- VACUUM ANALYZE pmoves.youtube_videos;

-- Monitor index usage
-- SELECT schemaname, tablename, indexname, idx_scan, idx_tup_read, idx_tup_fetch
-- FROM pg_stat_user_indexes
-- WHERE schemaname = 'pmoves'
-- ORDER BY idx_scan;

COMMENT ON SCHEMA pmoves IS 'PMOVES.AI YouTube RAG System with CoCa embeddings';
COMMENT ON TABLE pmoves.youtube_segments IS 'Stores transcript segments with multi-level CoCa embeddings';
COMMENT ON FUNCTION pmoves.coca_hybrid_search IS 'Advanced hybrid search combining CoCa vectors and keywords';