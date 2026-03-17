-- Cast TTS Gateway: voice profiles + scheduled announcements persistence
-- Run against the pmoves_core schema in Supabase Postgres.

CREATE SCHEMA IF NOT EXISTS pmoves_core;

-- Voice profiles ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS pmoves_core.cast_voice_profiles (
    name        TEXT PRIMARY KEY,
    voice       TEXT NOT NULL DEFAULT 'default',
    speed       REAL NOT NULL DEFAULT 1.0,
    pitch       REAL NOT NULL DEFAULT 1.0,
    device      TEXT,
    "group"     TEXT,
    context_tags JSONB DEFAULT '[]'::jsonb,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE pmoves_core.cast_voice_profiles ENABLE ROW LEVEL SECURITY;

-- Service-role bypass (cast-tts-gateway uses service key)
CREATE POLICY cast_voice_profiles_service_bypass
    ON pmoves_core.cast_voice_profiles
    FOR ALL
    USING (current_setting('request.jwt.claim.role', true) = 'service_role');

-- Scheduled announcements -------------------------------------------------
CREATE TABLE IF NOT EXISTS pmoves_core.cast_scheduled_announcements (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    text           TEXT NOT NULL,
    cron           TEXT,
    schedule_type  TEXT NOT NULL DEFAULT 'cron',
    enabled        BOOLEAN NOT NULL DEFAULT true,
    run_count      INTEGER NOT NULL DEFAULT 0,
    device         TEXT,
    "group"        TEXT,
    voice          TEXT DEFAULT 'default',
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE pmoves_core.cast_scheduled_announcements ENABLE ROW LEVEL SECURITY;

CREATE POLICY cast_scheduled_service_bypass
    ON pmoves_core.cast_scheduled_announcements
    FOR ALL
    USING (current_setting('request.jwt.claim.role', true) = 'service_role');
