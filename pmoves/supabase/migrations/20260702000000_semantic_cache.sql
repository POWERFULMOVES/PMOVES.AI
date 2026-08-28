-- Semantic Cache for LLM Inference (#1427)
-- Three-layer architecture: Cipher KG → pgvector → TensorZero

CREATE SCHEMA IF NOT EXISTS pmoves_cache;

CREATE TABLE IF NOT EXISTS pmoves_cache.llm_semantic_cache (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Cache key components (tool-schema-aware)
    cache_key TEXT NOT NULL UNIQUE,
    query_text TEXT NOT NULL,
    model TEXT NOT NULL,
    
    -- Embedding (max dimension across models: OpenAI 3072d)
    query_embedding vector(3072),
    embedding_model TEXT,
    embedding_dim INTEGER,
    
    -- BGE-M3 multi-dimensional support (optional)
    query_sparse JSONB,
    query_colbert JSONB,
    
    -- Cached response
    response_json JSONB NOT NULL,
    
    -- TTL + lifecycle
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at TIMESTAMPTZ NOT NULL,
    access_count INTEGER NOT NULL DEFAULT 0,
    last_accessed_at TIMESTAMPTZ,
    
    -- Cipher integration (Layer 0)
    cipher_memory_id TEXT,
    
    -- Tokenism attribution
    tokens_saved INTEGER,
    cost_saved_usd NUMERIC(10, 6)
);

-- HNSW index for fast cosine similarity search
CREATE INDEX IF NOT EXISTS idx_semantic_cache_embedding_hnsw
    ON pmoves_cache.llm_semantic_cache
    USING hnsw ((query_embedding::halfvec(3072)) halfvec_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- Index for TTL eviction
CREATE INDEX IF NOT EXISTS idx_semantic_cache_expires
    ON pmoves_cache.llm_semantic_cache (expires_at);

-- Index for cache key lookups (exact match)
CREATE INDEX IF NOT EXISTS idx_semantic_cache_key
    ON pmoves_cache.llm_semantic_cache (cache_key);

-- Index for model filtering
CREATE INDEX IF NOT EXISTS idx_semantic_cache_model
    ON pmoves_cache.llm_semantic_cache (model);

-- RPC function for similarity search with TTL filtering
CREATE OR REPLACE FUNCTION pmoves_cache.search_semantic_cache(
    p_embedding vector(3072),
    p_model TEXT,
    p_similarity_threshold FLOAT DEFAULT 0.90,
    p_max_results INTEGER DEFAULT 1
)
RETURNS TABLE (
    id UUID,
    query_text TEXT,
    response_json JSONB,
    similarity FLOAT,
    model TEXT,
    tokens_saved INTEGER
)
LANGUAGE sql
STABLE
AS $$
    SELECT
        c.id,
        c.query_text,
        c.response_json,
        1.0 - (c.query_embedding <=> p_embedding) AS similarity,
        c.model,
        c.tokens_saved
    FROM pmoves_cache.llm_semantic_cache c
    WHERE c.expires_at > now()
      AND c.model = p_model
      AND 1.0 - (c.query_embedding <=> p_embedding) >= p_similarity_threshold
    ORDER BY c.query_embedding <=> p_embedding
    LIMIT p_max_results;
$$;

-- Auto-eviction function (call from cron or on insert)
CREATE OR REPLACE FUNCTION pmoves_cache.evict_expired()
RETURNS INTEGER
LANGUAGE sql
AS $$
    DELETE FROM pmoves_cache.llm_semantic_cache
    WHERE expires_at < now()
    RETURNING 1;
$$;

COMMENT ON SCHEMA pmoves_cache IS 'Semantic cache for LLM inference (#1427)';
COMMENT ON TABLE pmoves_cache.llm_semantic_cache IS 'pgvector-powered semantic cache with HNSW index, TTL, Cipher KG integration, and Tokenism attribution';
