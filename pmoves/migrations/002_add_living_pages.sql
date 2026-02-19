-- Migration: Add Living Pages table for Open Notebook → Supabase sync
-- Thread 6.2: Living Pages Schema
-- RLS: service_role only (NOT USING (true) — see Phase C audit)

BEGIN;

-- Living Pages: synced content from Open Notebook (SurrealDB)
CREATE TABLE IF NOT EXISTS pmoves_core.living_pages (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    notebook_id     TEXT NOT NULL,
    title           TEXT,
    content_text    TEXT,
    content_json    JSONB,
    cgp_packet      JSONB,
    source_url      TEXT,
    tags            TEXT[] DEFAULT '{}',
    word_count      INTEGER DEFAULT 0,
    language        TEXT DEFAULT 'en',
    indexed         BOOLEAN DEFAULT FALSE,
    indexed_at      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (notebook_id)
);

-- Model Bindings: HuggingFace model onboarding records (Thread 1.2)
CREATE TABLE IF NOT EXISTS pmoves_core.model_bindings (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    model_id        TEXT NOT NULL,
    name            TEXT NOT NULL,
    author          TEXT,
    task            TEXT,
    params          BIGINT,
    context_length  INTEGER,
    license         TEXT,
    tier            TEXT DEFAULT 'medium',
    capabilities    TEXT[] DEFAULT '{}',
    performance     JSONB DEFAULT '{}',
    hf_url          TEXT,
    cgp_fragment    JSONB,
    onboarded_at    TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (model_id)
);

-- Swarm Attribution records (Thread 3.5)
CREATE TABLE IF NOT EXISTS pmoves_core.swarm_attribution (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id        TEXT NOT NULL,
    task_id         TEXT,
    namespace       TEXT DEFAULT 'pmoves.agents',
    fitness         DOUBLE PRECISION,
    weights         JSONB,
    metrics         JSONB,
    generation      INTEGER DEFAULT 0,
    population_id   TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_living_pages_notebook_id
    ON pmoves_core.living_pages (notebook_id);
CREATE INDEX IF NOT EXISTS idx_living_pages_updated
    ON pmoves_core.living_pages (updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_living_pages_tags
    ON pmoves_core.living_pages USING GIN (tags);
CREATE INDEX IF NOT EXISTS idx_living_pages_content_json
    ON pmoves_core.living_pages USING GIN (content_json jsonb_path_ops);

CREATE INDEX IF NOT EXISTS idx_model_bindings_model_id
    ON pmoves_core.model_bindings (model_id);
CREATE INDEX IF NOT EXISTS idx_model_bindings_tier
    ON pmoves_core.model_bindings (tier);
CREATE INDEX IF NOT EXISTS idx_model_bindings_capabilities
    ON pmoves_core.model_bindings USING GIN (capabilities);

CREATE INDEX IF NOT EXISTS idx_swarm_attribution_agent
    ON pmoves_core.swarm_attribution (agent_id);
CREATE INDEX IF NOT EXISTS idx_swarm_attribution_task
    ON pmoves_core.swarm_attribution (task_id);

-- RLS: service_role only (fail-closed, NOT USING (true))
ALTER TABLE pmoves_core.living_pages ENABLE ROW LEVEL SECURITY;
ALTER TABLE pmoves_core.model_bindings ENABLE ROW LEVEL SECURITY;
ALTER TABLE pmoves_core.swarm_attribution ENABLE ROW LEVEL SECURITY;

CREATE POLICY IF NOT EXISTS living_pages_service_only
    ON pmoves_core.living_pages
    FOR ALL
    USING (auth.role() = 'service_role')
    WITH CHECK (auth.role() = 'service_role');

CREATE POLICY IF NOT EXISTS model_bindings_service_only
    ON pmoves_core.model_bindings
    FOR ALL
    USING (auth.role() = 'service_role')
    WITH CHECK (auth.role() = 'service_role');

CREATE POLICY IF NOT EXISTS swarm_attribution_service_only
    ON pmoves_core.swarm_attribution
    FOR ALL
    USING (auth.role() = 'service_role')
    WITH CHECK (auth.role() = 'service_role');

-- Updated_at trigger
CREATE OR REPLACE FUNCTION pmoves_core.update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER living_pages_updated_at
    BEFORE UPDATE ON pmoves_core.living_pages
    FOR EACH ROW EXECUTE FUNCTION pmoves_core.update_updated_at();

CREATE TRIGGER model_bindings_updated_at
    BEFORE UPDATE ON pmoves_core.model_bindings
    FOR EACH ROW EXECUTE FUNCTION pmoves_core.update_updated_at();

COMMIT;
