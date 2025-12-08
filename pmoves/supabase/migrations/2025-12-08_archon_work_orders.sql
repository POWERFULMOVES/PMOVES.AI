-- Archon Agent Work Orders Tables
-- Migration: 2025-12-08_archon_work_orders.sql
-- Purpose: Database schema for Archon Agent Work Orders service (port 8053)
-- Service: Autonomous workflow execution via Claude Code CLI

-- ============================================================================
-- Table: archon_configured_repositories
-- Purpose: Store GitHub repository configurations with verification status
-- and per-repository workflow preferences
-- ============================================================================

CREATE TABLE IF NOT EXISTS archon_configured_repositories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    repository_url TEXT NOT NULL UNIQUE,
    display_name TEXT,
    owner TEXT,
    default_branch TEXT,
    is_verified BOOLEAN DEFAULT FALSE,
    last_verified_at TIMESTAMPTZ,
    default_sandbox_type TEXT DEFAULT 'git_worktree' CHECK (
        default_sandbox_type IN ('git_branch', 'git_worktree', 'e2b', 'dagger')
    ),
    default_commands JSONB DEFAULT '["create-branch", "planning", "execute", "commit", "create-pr"]'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

-- Index for fast lookups by repository URL
CREATE INDEX IF NOT EXISTS idx_archon_configured_repositories_url
    ON archon_configured_repositories(repository_url);

-- Index for listing verified repositories
CREATE INDEX IF NOT EXISTS idx_archon_configured_repositories_verified
    ON archon_configured_repositories(is_verified) WHERE is_verified = TRUE;

COMMENT ON TABLE archon_configured_repositories IS
    'GitHub repository configurations for Agent Work Orders with verification status and workflow preferences';

-- ============================================================================
-- Table: archon_agent_work_orders
-- Purpose: Store agent work order state with minimal core fields
-- Core fields are persisted, computed fields derived from git at runtime
-- ============================================================================

CREATE TABLE IF NOT EXISTS archon_agent_work_orders (
    -- Primary key
    agent_work_order_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Core state fields (minimal persistent state)
    repository_url TEXT NOT NULL REFERENCES archon_configured_repositories(repository_url)
        ON DELETE CASCADE ON UPDATE CASCADE,
    sandbox_identifier TEXT NOT NULL,
    git_branch_name TEXT,
    agent_session_id TEXT,

    -- Metadata fields
    sandbox_type TEXT NOT NULL DEFAULT 'git_worktree' CHECK (
        sandbox_type IN ('git_branch', 'git_worktree', 'e2b', 'dagger')
    ),
    github_issue_number TEXT,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (
        status IN ('pending', 'running', 'completed', 'failed')
    ),
    current_phase TEXT CHECK (
        current_phase IS NULL OR current_phase IN ('planning', 'completed')
    ),
    user_request TEXT NOT NULL,
    selected_commands JSONB DEFAULT '["create-branch", "planning", "execute", "commit", "create-pr"]'::jsonb,

    -- Computed fields (populated by service, derived from git)
    github_pull_request_url TEXT,
    git_commit_count INTEGER DEFAULT 0,
    git_files_changed INTEGER DEFAULT 0,
    error_message TEXT,

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

-- Index for listing work orders by status
CREATE INDEX IF NOT EXISTS idx_archon_work_orders_status
    ON archon_agent_work_orders(status);

-- Index for listing work orders by repository
CREATE INDEX IF NOT EXISTS idx_archon_work_orders_repository
    ON archon_agent_work_orders(repository_url);

-- Index for finding active work orders (pending or running)
CREATE INDEX IF NOT EXISTS idx_archon_work_orders_active
    ON archon_agent_work_orders(status) WHERE status IN ('pending', 'running');

-- Index for finding work orders by session
CREATE INDEX IF NOT EXISTS idx_archon_work_orders_session
    ON archon_agent_work_orders(agent_session_id) WHERE agent_session_id IS NOT NULL;

-- Index for finding work orders by branch
CREATE INDEX IF NOT EXISTS idx_archon_work_orders_branch
    ON archon_agent_work_orders(git_branch_name) WHERE git_branch_name IS NOT NULL;

COMMENT ON TABLE archon_agent_work_orders IS
    'Agent work orders for Claude Code CLI workflow automation with minimal persistent state';

-- ============================================================================
-- Table: archon_agent_work_order_steps
-- Purpose: Store execution history for each workflow step
-- Provides audit trail and retry information
-- ============================================================================

CREATE TABLE IF NOT EXISTS archon_agent_work_order_steps (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_work_order_id UUID NOT NULL REFERENCES archon_agent_work_orders(agent_work_order_id)
        ON DELETE CASCADE ON UPDATE CASCADE,
    step TEXT NOT NULL CHECK (
        step IN ('create-branch', 'planning', 'execute', 'commit', 'create-pr', 'prp-review')
    ),
    agent_name TEXT NOT NULL,
    success BOOLEAN NOT NULL,
    output TEXT,
    error_message TEXT,
    duration_seconds FLOAT,
    session_id TEXT,
    timestamp TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

-- Index for listing steps by work order (chronological)
CREATE INDEX IF NOT EXISTS idx_archon_work_order_steps_order
    ON archon_agent_work_order_steps(agent_work_order_id, timestamp);

-- Index for finding failed steps (for retry logic)
CREATE INDEX IF NOT EXISTS idx_archon_work_order_steps_failed
    ON archon_agent_work_order_steps(agent_work_order_id, success) WHERE success = FALSE;

-- Index for step type analysis
CREATE INDEX IF NOT EXISTS idx_archon_work_order_steps_type
    ON archon_agent_work_order_steps(step);

COMMENT ON TABLE archon_agent_work_order_steps IS
    'Execution history for workflow steps with timing and output capture';

-- ============================================================================
-- Trigger: Auto-update updated_at timestamp
-- ============================================================================

CREATE OR REPLACE FUNCTION update_archon_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_archon_configured_repositories_updated ON archon_configured_repositories;
CREATE TRIGGER trg_archon_configured_repositories_updated
    BEFORE UPDATE ON archon_configured_repositories
    FOR EACH ROW EXECUTE FUNCTION update_archon_updated_at();

DROP TRIGGER IF EXISTS trg_archon_agent_work_orders_updated ON archon_agent_work_orders;
CREATE TRIGGER trg_archon_agent_work_orders_updated
    BEFORE UPDATE ON archon_agent_work_orders
    FOR EACH ROW EXECUTE FUNCTION update_archon_updated_at();

-- ============================================================================
-- Row Level Security (RLS) Policies
-- ============================================================================

-- Enable RLS on all tables
ALTER TABLE archon_configured_repositories ENABLE ROW LEVEL SECURITY;
ALTER TABLE archon_agent_work_orders ENABLE ROW LEVEL SECURITY;
ALTER TABLE archon_agent_work_order_steps ENABLE ROW LEVEL SECURITY;

-- Policy: service_role has full access
DROP POLICY IF EXISTS archon_configured_repositories_service_role ON archon_configured_repositories;
CREATE POLICY archon_configured_repositories_service_role
    ON archon_configured_repositories
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

DROP POLICY IF EXISTS archon_agent_work_orders_service_role ON archon_agent_work_orders;
CREATE POLICY archon_agent_work_orders_service_role
    ON archon_agent_work_orders
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

DROP POLICY IF EXISTS archon_agent_work_order_steps_service_role ON archon_agent_work_order_steps;
CREATE POLICY archon_agent_work_order_steps_service_role
    ON archon_agent_work_order_steps
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Policy: authenticated users can read all, write own work orders
DROP POLICY IF EXISTS archon_configured_repositories_authenticated ON archon_configured_repositories;
CREATE POLICY archon_configured_repositories_authenticated
    ON archon_configured_repositories
    FOR SELECT
    TO authenticated
    USING (true);

DROP POLICY IF EXISTS archon_agent_work_orders_authenticated ON archon_agent_work_orders;
CREATE POLICY archon_agent_work_orders_authenticated
    ON archon_agent_work_orders
    FOR SELECT
    TO authenticated
    USING (true);

DROP POLICY IF EXISTS archon_agent_work_order_steps_authenticated ON archon_agent_work_order_steps;
CREATE POLICY archon_agent_work_order_steps_authenticated
    ON archon_agent_work_order_steps
    FOR SELECT
    TO authenticated
    USING (true);

-- ============================================================================
-- Views for convenient querying
-- ============================================================================

-- View: Active work orders with latest step
CREATE OR REPLACE VIEW archon_active_work_orders AS
SELECT
    wo.agent_work_order_id,
    wo.repository_url,
    wo.sandbox_identifier,
    wo.sandbox_type,
    wo.status,
    wo.current_phase,
    wo.user_request,
    wo.git_branch_name,
    wo.github_pull_request_url,
    wo.created_at,
    wo.updated_at,
    (
        SELECT step FROM archon_agent_work_order_steps s
        WHERE s.agent_work_order_id = wo.agent_work_order_id
        ORDER BY timestamp DESC LIMIT 1
    ) AS latest_step,
    (
        SELECT count(*) FROM archon_agent_work_order_steps s
        WHERE s.agent_work_order_id = wo.agent_work_order_id
    ) AS total_steps
FROM archon_agent_work_orders wo
WHERE wo.status IN ('pending', 'running')
ORDER BY wo.created_at DESC;

COMMENT ON VIEW archon_active_work_orders IS
    'Active work orders (pending or running) with latest step information';

-- View: Work order summary with step counts
CREATE OR REPLACE VIEW archon_work_order_summary AS
SELECT
    wo.agent_work_order_id,
    wo.repository_url,
    wo.status,
    wo.user_request,
    wo.git_branch_name,
    wo.github_pull_request_url,
    wo.created_at,
    wo.updated_at,
    (
        SELECT count(*) FROM archon_agent_work_order_steps s
        WHERE s.agent_work_order_id = wo.agent_work_order_id AND s.success = true
    ) AS successful_steps,
    (
        SELECT count(*) FROM archon_agent_work_order_steps s
        WHERE s.agent_work_order_id = wo.agent_work_order_id AND s.success = false
    ) AS failed_steps,
    (
        SELECT sum(duration_seconds) FROM archon_agent_work_order_steps s
        WHERE s.agent_work_order_id = wo.agent_work_order_id
    ) AS total_duration_seconds
FROM archon_agent_work_orders wo
ORDER BY wo.created_at DESC;

COMMENT ON VIEW archon_work_order_summary IS
    'Work order summary with execution statistics';

-- ============================================================================
-- Functions for common operations
-- ============================================================================

-- Function: Get next step for a work order
CREATE OR REPLACE FUNCTION get_next_work_order_step(work_order_id UUID)
RETURNS TEXT AS $$
DECLARE
    last_step RECORD;
    step_sequence TEXT[] := ARRAY['create-branch', 'planning', 'execute', 'commit', 'create-pr'];
    current_index INT;
BEGIN
    -- Get the last step
    SELECT step, success INTO last_step
    FROM archon_agent_work_order_steps
    WHERE agent_work_order_id = work_order_id
    ORDER BY timestamp DESC
    LIMIT 1;

    -- If no steps yet, return first step
    IF last_step IS NULL THEN
        RETURN 'create-branch';
    END IF;

    -- If last step failed, retry it
    IF NOT last_step.success THEN
        RETURN last_step.step;
    END IF;

    -- Find current step index and return next
    FOR i IN 1..array_length(step_sequence, 1) LOOP
        IF step_sequence[i] = last_step.step THEN
            current_index := i;
            EXIT;
        END IF;
    END LOOP;

    -- Return next step or NULL if complete
    IF current_index < array_length(step_sequence, 1) THEN
        RETURN step_sequence[current_index + 1];
    ELSE
        RETURN NULL;
    END IF;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION get_next_work_order_step IS
    'Get the next step to execute for a work order based on execution history';

-- Function: Get work order by session ID
CREATE OR REPLACE FUNCTION get_work_order_by_session(session_id TEXT)
RETURNS UUID AS $$
BEGIN
    RETURN (
        SELECT agent_work_order_id
        FROM archon_agent_work_orders
        WHERE agent_session_id = session_id
        LIMIT 1
    );
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION get_work_order_by_session IS
    'Find a work order by its Claude CLI session ID';

-- ============================================================================
-- Sample data for testing (commented out for production)
-- ============================================================================

-- Uncomment to insert sample repository for testing:
-- INSERT INTO archon_configured_repositories (repository_url, display_name, owner, default_branch, is_verified)
-- VALUES ('https://github.com/frostbytten/PMOVES.AI', 'frostbytten/PMOVES.AI', 'frostbytten', 'main', true);
