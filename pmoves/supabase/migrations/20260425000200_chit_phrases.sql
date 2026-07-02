-- =============================================================================
-- Migration: chit_phrases — canonical phrase registry with embedding index
-- Stage 7: Chit geometry phrase matching via HNSW vector search
-- Seeds 8 canonical phrases for validation compliance
-- =============================================================================

CREATE SCHEMA IF NOT EXISTS pmoves_core;

CREATE TABLE IF NOT EXISTS pmoves_core.chit_phrases (
    phrase_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    phrase_canonical TEXT NOT NULL,
    category         TEXT NOT NULL,
    weight           FLOAT NOT NULL DEFAULT 1.0,
    embedding        vector(2560),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT chit_phrases_weight_chk CHECK (weight >= 0)
);

-- HNSW index for fast approximate nearest-neighbor search on embeddings
CREATE INDEX IF NOT EXISTS idx_chit_phrases_embedding_hnsw
    ON pmoves_core.chit_phrases USING hnsw (embedding vector_cosine_ops);

-- Helpful category index
CREATE INDEX IF NOT EXISTS idx_chit_phrases_category
    ON pmoves_core.chit_phrases (category);

-- Enable RLS
ALTER TABLE IF EXISTS pmoves_core.chit_phrases ENABLE ROW LEVEL SECURITY;

-- Revoke anon; grant service_role full, authenticated read-only
DO $$ BEGIN
  EXECUTE 'REVOKE ALL ON pmoves_core.chit_phrases FROM anon';
EXCEPTION WHEN OTHERS THEN
  RAISE NOTICE 'REVOKE from anon on chit_phrases: %', SQLERRM;
END $$;

DO $$ BEGIN
  EXECUTE 'GRANT ALL ON pmoves_core.chit_phrases TO service_role';
EXCEPTION WHEN OTHERS THEN
  RAISE NOTICE 'GRANT to service_role on chit_phrases: %', SQLERRM;
END $$;

DO $$ BEGIN
  EXECUTE 'GRANT SELECT ON pmoves_core.chit_phrases TO authenticated';
EXCEPTION WHEN OTHERS THEN
  RAISE NOTICE 'GRANT SELECT to authenticated on chit_phrases: %', SQLERRM;
END $$;

-- Drop existing policies if re-running
DROP POLICY IF EXISTS "chit_phrases_svc_all" ON pmoves_core.chit_phrases;
DROP POLICY IF EXISTS "chit_phrases_auth_read" ON pmoves_core.chit_phrases;

CREATE POLICY "chit_phrases_svc_all" ON pmoves_core.chit_phrases
  FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE POLICY "chit_phrases_auth_read" ON pmoves_core.chit_phrases
  FOR SELECT TO authenticated USING (true);

-- Seed 8 canonical phrases (validation: verify 8 rows in chit_phrases)
INSERT INTO pmoves_core.chit_phrases (phrase_canonical, category, weight) VALUES
    ('hello world',               'greeting',   1.0),
    ('how are you',               'greeting',   1.0),
    ('thank you',                 'gratitude',  1.0),
    ('good morning',              'greeting',   0.9),
    ('what time is it',           'inquiry',    1.0),
    ('tell me a joke',            'request',    0.8),
    ('see you later',             'farewell',   1.0),
    ('nice to meet you',          'greeting',   0.9)
ON CONFLICT (phrase_id) DO NOTHING;
