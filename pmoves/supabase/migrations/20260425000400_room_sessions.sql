-- =============================================================================
-- Migration: room_sessions — multi-agent room lifecycle tracking
-- Stage 10: Room manifest session state with active/paused/ended/archived states
-- FK to room manifest, indexed on room_id + state for fast active-room lookups
-- =============================================================================

CREATE SCHEMA IF NOT EXISTS pmoves_core;

CREATE TABLE IF NOT EXISTS pmoves_core.room_sessions (
    session_id   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    room_id      TEXT NOT NULL,
    agent_id     TEXT,
    started_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    ended_at     TIMESTAMPTZ,
    state        TEXT NOT NULL DEFAULT 'active',
    metadata     JSONB,

    CONSTRAINT room_sessions_state_chk
        CHECK (state IN ('active', 'paused', 'ended', 'archived')),
    CONSTRAINT room_sessions_ended_after_started_chk
        CHECK (ended_at IS NULL OR ended_at >= started_at)
);

-- Indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_room_sessions_room_id
    ON pmoves_core.room_sessions (room_id);

CREATE INDEX IF NOT EXISTS idx_room_sessions_state
    ON pmoves_core.room_sessions (state);

-- Composite index for active-room-by-room lookups
CREATE INDEX IF NOT EXISTS idx_room_sessions_room_id_state
    ON pmoves_core.room_sessions (room_id, state);

-- Enable RLS
ALTER TABLE IF EXISTS pmoves_core.room_sessions ENABLE ROW LEVEL SECURITY;

-- Revoke anon; grant service_role full, authenticated read
DO $$ BEGIN
  EXECUTE 'GRANT USAGE ON SCHEMA pmoves_core TO service_role, authenticated';
EXCEPTION WHEN OTHERS THEN
  RAISE NOTICE 'GRANT USAGE on pmoves_core: %', SQLERRM;
END $$;

DO $$ BEGIN
  EXECUTE 'REVOKE ALL ON pmoves_core.room_sessions FROM anon';
EXCEPTION WHEN OTHERS THEN
  RAISE NOTICE 'REVOKE from anon on room_sessions: %', SQLERRM;
END $$;

DO $$ BEGIN
  EXECUTE 'GRANT ALL ON pmoves_core.room_sessions TO service_role';
EXCEPTION WHEN OTHERS THEN
  RAISE NOTICE 'GRANT to service_role on room_sessions: %', SQLERRM;
END $$;

DO $$ BEGIN
  EXECUTE 'GRANT SELECT ON pmoves_core.room_sessions TO authenticated';
EXCEPTION WHEN OTHERS THEN
  RAISE NOTICE 'GRANT SELECT to authenticated on room_sessions: %', SQLERRM;
END $$;

-- Drop existing policies if re-running
DROP POLICY IF EXISTS "room_sessions_svc_all" ON pmoves_core.room_sessions;
DROP POLICY IF EXISTS "room_sessions_auth_read" ON pmoves_core.room_sessions;

CREATE POLICY "room_sessions_svc_all" ON pmoves_core.room_sessions
  FOR ALL TO service_role USING (auth.role() = 'service_role') WITH CHECK (auth.role() = 'service_role');

CREATE POLICY "room_sessions_auth_read" ON pmoves_core.room_sessions
  FOR SELECT TO authenticated USING (auth.uid() IS NOT NULL);
