-- Claude Code Session Context Persistence
-- Stores session context for Claude Code CLI autocompact recovery
-- Enables: Supabase Realtime subscriptions, Hi-RAG ingestion, Discord threading

-- ============================================================================
-- TABLE: claude_sessions
-- ============================================================================

CREATE TABLE IF NOT EXISTS pmoves_core.claude_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Session identification
    session_id TEXT NOT NULL,
    context_type TEXT NOT NULL CHECK (context_type IN ('autocompact', 'checkpoint', 'tool', 'decision', 'summary', 'start', 'end')),

    -- Git context
    worktree TEXT,
    branch TEXT,
    repository TEXT DEFAULT 'PMOVES.AI',
    working_directory TEXT,

    -- Content
    summary TEXT,
    active_files JSONB DEFAULT '[]'::jsonb,
    pending_tasks JSONB DEFAULT '[]'::jsonb,
    decisions JSONB DEFAULT '[]'::jsonb,
    tool_executions JSONB DEFAULT '[]'::jsonb,
    agent_spawns JSONB DEFAULT '[]'::jsonb,

    -- CHIT Geometry Bus integration
    cgp_geometry JSONB,

    -- Session linking
    parent_session_id TEXT,

    -- End session metadata
    end_reason TEXT CHECK (end_reason IS NULL OR end_reason IN ('completed', 'autocompact', 'user_exit', 'error', 'timeout')),
    duration_seconds INTEGER,
    files_modified JSONB DEFAULT '[]'::jsonb,
    commits_created JSONB DEFAULT '[]'::jsonb,

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- Full raw payload for debugging
    raw_payload JSONB
);

-- Index for fast session lookups
CREATE INDEX IF NOT EXISTS idx_claude_sessions_session_id
    ON pmoves_core.claude_sessions(session_id);

CREATE INDEX IF NOT EXISTS idx_claude_sessions_context_type
    ON pmoves_core.claude_sessions(context_type);

CREATE INDEX IF NOT EXISTS idx_claude_sessions_worktree
    ON pmoves_core.claude_sessions(worktree)
    WHERE worktree IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_claude_sessions_branch
    ON pmoves_core.claude_sessions(branch)
    WHERE branch IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_claude_sessions_created_at
    ON pmoves_core.claude_sessions(created_at DESC);

-- GIN index for JSONB searches
CREATE INDEX IF NOT EXISTS idx_claude_sessions_pending_tasks
    ON pmoves_core.claude_sessions USING GIN (pending_tasks);

CREATE INDEX IF NOT EXISTS idx_claude_sessions_active_files
    ON pmoves_core.claude_sessions USING GIN (active_files);

-- ============================================================================
-- TRIGGER: Updated timestamp
-- ============================================================================

CREATE OR REPLACE FUNCTION pmoves_core.update_claude_sessions_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_claude_sessions_updated_at ON pmoves_core.claude_sessions;
CREATE TRIGGER trigger_claude_sessions_updated_at
    BEFORE UPDATE ON pmoves_core.claude_sessions
    FOR EACH ROW
    EXECUTE FUNCTION pmoves_core.update_claude_sessions_updated_at();

-- ============================================================================
-- ROW LEVEL SECURITY
-- ============================================================================

ALTER TABLE pmoves_core.claude_sessions ENABLE ROW LEVEL SECURITY;

-- Service role has full access
CREATE POLICY claude_sessions_service_all ON pmoves_core.claude_sessions
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Authenticated users can read their sessions (by repository access)
CREATE POLICY claude_sessions_authenticated_select ON pmoves_core.claude_sessions
    FOR SELECT
    TO authenticated
    USING (true);

-- ============================================================================
-- REALTIME: Enable for live subscriptions
-- ============================================================================

-- Enable realtime for the table
ALTER PUBLICATION supabase_realtime ADD TABLE pmoves_core.claude_sessions;

-- ============================================================================
-- VIEW: Latest session context per session_id
-- ============================================================================

CREATE OR REPLACE VIEW pmoves_core.claude_sessions_latest AS
SELECT DISTINCT ON (session_id)
    id,
    session_id,
    context_type,
    worktree,
    branch,
    repository,
    working_directory,
    summary,
    active_files,
    pending_tasks,
    decisions,
    tool_executions,
    agent_spawns,
    cgp_geometry,
    parent_session_id,
    end_reason,
    duration_seconds,
    files_modified,
    commits_created,
    created_at,
    updated_at
FROM pmoves_core.claude_sessions
ORDER BY session_id, created_at DESC;

COMMENT ON VIEW pmoves_core.claude_sessions_latest IS
    'Latest context snapshot for each Claude Code session';

-- ============================================================================
-- VIEW: Active sessions (no end event)
-- ============================================================================

CREATE OR REPLACE VIEW pmoves_core.claude_sessions_active AS
SELECT
    sl.session_id,
    sl.worktree,
    sl.branch,
    sl.summary,
    sl.pending_tasks,
    sl.created_at as last_activity,
    (NOW() - sl.created_at) as idle_duration
FROM pmoves_core.claude_sessions_latest sl
WHERE sl.context_type != 'end'
  AND sl.end_reason IS NULL
  AND sl.created_at > NOW() - INTERVAL '24 hours'
ORDER BY sl.created_at DESC;

COMMENT ON VIEW pmoves_core.claude_sessions_active IS
    'Currently active Claude Code sessions';

-- ============================================================================
-- FUNCTION: Get session continuation context
-- ============================================================================

CREATE OR REPLACE FUNCTION pmoves_core.get_session_continuation(
    p_session_id TEXT
)
RETURNS JSONB AS $$
DECLARE
    v_context JSONB;
BEGIN
    SELECT jsonb_build_object(
        'session_id', session_id,
        'worktree', worktree,
        'branch', branch,
        'summary', summary,
        'pending_tasks', pending_tasks,
        'active_files', active_files,
        'decisions', decisions,
        'cgp_geometry', cgp_geometry,
        'last_updated', created_at
    )
    INTO v_context
    FROM pmoves_core.claude_sessions_latest
    WHERE session_id = p_session_id;

    RETURN COALESCE(v_context, '{}'::jsonb);
END;
$$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION pmoves_core.get_session_continuation IS
    'Get the latest context for a session to enable continuation after autocompact';

-- ============================================================================
-- FUNCTION: Search sessions by task content
-- ============================================================================

CREATE OR REPLACE FUNCTION pmoves_core.search_claude_sessions(
    p_query TEXT,
    p_limit INTEGER DEFAULT 10
)
RETURNS TABLE (
    session_id TEXT,
    worktree TEXT,
    branch TEXT,
    summary TEXT,
    created_at TIMESTAMPTZ,
    relevance REAL
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        cs.session_id,
        cs.worktree,
        cs.branch,
        cs.summary,
        cs.created_at,
        ts_rank(
            to_tsvector('english', COALESCE(cs.summary, '') || ' ' || COALESCE(cs.pending_tasks::text, '')),
            plainto_tsquery('english', p_query)
        ) as relevance
    FROM pmoves_core.claude_sessions cs
    WHERE to_tsvector('english', COALESCE(cs.summary, '') || ' ' || COALESCE(cs.pending_tasks::text, ''))
          @@ plainto_tsquery('english', p_query)
    ORDER BY relevance DESC, cs.created_at DESC
    LIMIT p_limit;
END;
$$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION pmoves_core.search_claude_sessions IS
    'Full-text search across Claude Code session summaries and tasks';
