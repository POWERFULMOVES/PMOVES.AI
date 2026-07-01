-- PMOVES v5.15 schema upgrade: Consciousness theories from Kuhn taxonomy
-- Creates tables for storing consciousness theories with vector embeddings

-- Ensure extensions are available
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS vector;

-- Consciousness theories table (in pmoves_core schema following existing pattern)
CREATE TABLE IF NOT EXISTS pmoves_core.consciousness_theories (
  id          text PRIMARY KEY,
  title       text NOT NULL,
  url         text,
  category    text NOT NULL,
  content     text NOT NULL,
  namespace   text NOT NULL DEFAULT 'pmoves.consciousness',
  created_at  timestamptz NOT NULL DEFAULT now(),
  updated_at  timestamptz NOT NULL DEFAULT now()
);

-- Indexes for querying
CREATE INDEX IF NOT EXISTS idx_consciousness_theories_category
  ON pmoves_core.consciousness_theories(category);
CREATE INDEX IF NOT EXISTS idx_consciousness_theories_namespace
  ON pmoves_core.consciousness_theories(namespace);
CREATE INDEX IF NOT EXISTS idx_consciousness_theories_created
  ON pmoves_core.consciousness_theories(created_at DESC);

-- Full-text search index
CREATE INDEX IF NOT EXISTS idx_consciousness_theories_content_trgm
  ON pmoves_core.consciousness_theories USING gin (content gin_trgm_ops);

-- Vector embedding index (created when embeddings are added)
-- DO $$ BEGIN
--   EXECUTE 'CREATE INDEX IF NOT EXISTS idx_consciousness_theories_embedding
--     ON pmoves_core.consciousness_theories USING ivfflat (embedding vector_cosine_ops)
--     WITH (lists = 100)';
-- EXCEPTION WHEN OTHERS THEN
--   RAISE NOTICE 'Skipping idx_consciousness_theories_embedding creation: %', SQLERRM;
-- END $$;

-- Comment for documentation
COMMENT ON TABLE pmoves_core.consciousness_theories IS
  'Consciousness theories from Robert Lawrence Kuhn''s Landscape of Consciousness taxonomy (325 theories)';
