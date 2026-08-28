-- DARKXSIDE playlist ingestion tracking table
-- Used by n8n flow darkxside_playlist_ingestion.json for dedup + progress tracking
CREATE TABLE IF NOT EXISTS pmoves_core.ingested_videos (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    video_id        TEXT NOT NULL UNIQUE,
    title           TEXT,
    status          TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','ingested','failed','skipped')),
    playlist_id     TEXT,
    persona         TEXT DEFAULT 'darkxside',
    room_id         TEXT DEFAULT 'darkxsides.room',
    duration        INTEGER,
    error           TEXT,
    ingested_at     TIMESTAMPTZ,
    failed_at       TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ingested_videos_status ON pmoves_core.ingested_videos (status);
CREATE INDEX IF NOT EXISTS idx_ingested_videos_persona ON pmoves_core.ingested_videos (persona);

ALTER TABLE pmoves_core.ingested_videos ENABLE ROW LEVEL SECURITY;
CREATE POLICY ingested_videos_service_all ON pmoves_core.ingested_videos
    FOR ALL TO service_role USING (true) WITH CHECK (true);
GRANT ALL ON pmoves_core.ingested_videos TO service_role;
GRANT SELECT ON pmoves_core.ingested_videos TO anon;
