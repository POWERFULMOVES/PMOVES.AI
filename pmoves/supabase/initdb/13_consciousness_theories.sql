-- PMOVES Consciousness Theories Schema
-- Creates tables for storing consciousness theories from Kuhn taxonomy

-- Consciousness theories table (in pmoves_core schema)
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

-- Comment for documentation
COMMENT ON TABLE pmoves_core.consciousness_theories IS
  'Consciousness theories from Robert Lawrence Kuhn''s Landscape of Consciousness taxonomy (325 theories)';
