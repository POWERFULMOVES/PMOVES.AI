-- v5.23: DARKXSIDE playlist enrichment — resonance taxonomy + School of PowerfulMoves
-- Adds columns for curriculum tracking, resonance domain mapping, resource link
-- extraction, and persona-driven content organization.

SET search_path TO pmoves_core;

-- Resonance domains (maps to agent_signatures.yaml resonance fields)
ALTER TABLE youtube_videos ADD COLUMN IF NOT EXISTS resonance_domain TEXT;
ALTER TABLE youtube_videos ADD COLUMN IF NOT EXISTS resonance_secondary TEXT[];

-- School of PowerfulMoves curriculum tracks
ALTER TABLE youtube_videos ADD COLUMN IF NOT EXISTS curriculum_track TEXT;
ALTER TABLE youtube_videos ADD COLUMN IF NOT EXISTS curriculum_subject TEXT;
ALTER TABLE youtube_videos ADD COLUMN IF NOT EXISTS difficulty_tier TEXT DEFAULT 'foundation';

-- Extracted resource links (github repos, docs, courses, tools)
ALTER TABLE youtube_videos ADD COLUMN IF NOT EXISTS resource_links JSONB DEFAULT '[]'::jsonb;

-- Persona signal — which PMOVES persona this video resonates with
ALTER TABLE youtube_videos ADD COLUMN IF NOT EXISTS persona_signal TEXT;

-- Nutrition/health/wealth integration flags
ALTER TABLE youtube_videos ADD COLUMN IF NOT EXISTS health_topic TEXT;
ALTER TABLE youtube_videos ADD COLUMN IF NOT EXISTS wealth_topic TEXT;

-- Index for curriculum queries
CREATE INDEX IF NOT EXISTS idx_yv_curriculum ON youtube_videos(curriculum_track, curriculum_subject);
CREATE INDEX IF NOT EXISTS idx_yv_resonance ON youtube_videos(resonance_domain);
CREATE INDEX IF NOT EXISTS idx_yv_health ON youtube_videos(health_topic) WHERE health_topic IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_yv_wealth ON youtube_videos(wealth_topic) WHERE wealth_topic IS NOT NULL;
