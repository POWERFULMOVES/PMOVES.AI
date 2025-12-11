-- PMOVES-BoTZ Work Items Registry
-- Tracks unimplemented work items per integration that BoTZ CLIs can auto-claim
-- Part of Phase 8: PMOVES-Crush CLI Integration & TAC Work Items Registry

-- Skill levels for BoTZ progression
DO $$ BEGIN
    CREATE TYPE skill_level AS ENUM (
        'basic',           -- Basic CLI operations
        'tac_enabled',     -- TAC commands and worktree management
        'mcp_augmented',   -- MCP tool integration
        'agentic'          -- Full orchestration capabilities
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Work item status tracking
DO $$ BEGIN
    CREATE TYPE work_item_status AS ENUM (
        'backlog',         -- Not ready for work
        'ready',           -- Available for claiming
        'in_progress',     -- Being worked on
        'completed',       -- Done
        'blocked'          -- Waiting on dependencies
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Work item priority levels
DO $$ BEGIN
    CREATE TYPE work_item_priority AS ENUM (
        'p0_critical',     -- Must be done immediately
        'p1_high',         -- Important, should be done soon
        'p2_medium',       -- Normal priority
        'p3_low'           -- Nice to have
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- BoTZ CLI Instance Registry
-- Tracks all registered BoTZ CLI instances and their capabilities
CREATE TABLE IF NOT EXISTS botz_instances (
    botz_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    botz_name TEXT NOT NULL,                            -- e.g., 'pmoves-crush', 'claude-code'
    instance_id TEXT UNIQUE NOT NULL,                   -- Unique instance identifier
    skill_level skill_level DEFAULT 'basic',
    available_mcp_tools JSONB DEFAULT '[]',             -- List of MCP tools available
    available_tac_commands JSONB DEFAULT '[]',          -- TAC commands enabled
    runner_host TEXT,                                   -- e.g., 'ai-lab', 'cloudstartup', 'local'
    config_path TEXT,                                   -- Path to crush.json or similar config
    last_heartbeat TIMESTAMPTZ DEFAULT now(),
    is_available BOOLEAN DEFAULT true,
    metadata JSONB DEFAULT '{}',                        -- Additional instance metadata
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- Integration Work Items Registry
-- Tracks unimplemented tasks per integration for BoTZ to claim
CREATE TABLE IF NOT EXISTS integration_work_items (
    work_item_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    integration_name TEXT NOT NULL,                     -- e.g., 'pmoves-crush', 'jellyfin', 'firefly'
    title TEXT NOT NULL,
    description TEXT,
    priority work_item_priority DEFAULT 'p2_medium',
    status work_item_status DEFAULT 'backlog',
    required_skill_level skill_level DEFAULT 'basic',   -- Minimum skill level to claim
    assigned_botz_id UUID REFERENCES botz_instances(botz_id),
    assigned_session_id TEXT,                           -- Claude session ID if applicable
    estimated_complexity TEXT,                          -- 'trivial', 'small', 'medium', 'large', 'epic'
    files_to_modify JSONB DEFAULT '[]',                 -- List of file paths to modify
    files_to_create JSONB DEFAULT '[]',                 -- List of new files to create
    required_mcp_tools JSONB DEFAULT '[]',              -- MCP tools needed for this item
    required_tac_commands JSONB DEFAULT '[]',           -- TAC commands needed
    dependencies JSONB DEFAULT '[]',                    -- Other work item IDs that must complete first
    tac_worktree TEXT,                                  -- Git worktree for this work
    tac_branch TEXT,                                    -- Git branch name
    pr_number INTEGER,                                  -- GitHub PR if created
    acceptance_criteria JSONB DEFAULT '[]',             -- List of criteria for completion
    metadata JSONB DEFAULT '{}',                        -- Additional metadata
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    completed_at TIMESTAMPTZ,
    claimed_at TIMESTAMPTZ
);

-- Work Item Execution History
-- Tracks attempts and progress on work items
CREATE TABLE IF NOT EXISTS work_item_executions (
    execution_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    work_item_id UUID NOT NULL REFERENCES integration_work_items(work_item_id),
    botz_id UUID NOT NULL REFERENCES botz_instances(botz_id),
    session_id TEXT,                                    -- Claude session ID
    status TEXT NOT NULL DEFAULT 'started',             -- 'started', 'in_progress', 'succeeded', 'failed', 'abandoned'
    started_at TIMESTAMPTZ DEFAULT now(),
    completed_at TIMESTAMPTZ,
    duration_seconds INTEGER,
    files_modified JSONB DEFAULT '[]',                  -- Files actually modified
    files_created JSONB DEFAULT '[]',                   -- Files actually created
    commit_sha TEXT,                                    -- Git commit if any
    pr_url TEXT,                                        -- PR URL if created
    error_message TEXT,                                 -- Error if failed
    logs JSONB DEFAULT '[]',                            -- Execution logs
    metrics JSONB DEFAULT '{}'                          -- Execution metrics
);

-- Indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_work_items_integration ON integration_work_items(integration_name);
CREATE INDEX IF NOT EXISTS idx_work_items_status ON integration_work_items(status);
CREATE INDEX IF NOT EXISTS idx_work_items_skill_level ON integration_work_items(required_skill_level);
CREATE INDEX IF NOT EXISTS idx_work_items_priority ON integration_work_items(priority);
CREATE INDEX IF NOT EXISTS idx_work_items_assigned ON integration_work_items(assigned_botz_id);
CREATE INDEX IF NOT EXISTS idx_work_items_ready ON integration_work_items(status, required_skill_level) WHERE status = 'ready';

CREATE INDEX IF NOT EXISTS idx_botz_instances_name ON botz_instances(botz_name);
CREATE INDEX IF NOT EXISTS idx_botz_instances_available ON botz_instances(is_available, skill_level);
CREATE INDEX IF NOT EXISTS idx_botz_instances_runner ON botz_instances(runner_host);

CREATE INDEX IF NOT EXISTS idx_executions_work_item ON work_item_executions(work_item_id);
CREATE INDEX IF NOT EXISTS idx_executions_botz ON work_item_executions(botz_id);
CREATE INDEX IF NOT EXISTS idx_executions_status ON work_item_executions(status);

-- Triggers for updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ language 'plpgsql';

DROP TRIGGER IF EXISTS update_botz_instances_updated_at ON botz_instances;
CREATE TRIGGER update_botz_instances_updated_at
    BEFORE UPDATE ON botz_instances
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_work_items_updated_at ON integration_work_items;
CREATE TRIGGER update_work_items_updated_at
    BEFORE UPDATE ON integration_work_items
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Function to claim a work item
CREATE OR REPLACE FUNCTION claim_work_item(
    p_work_item_id UUID,
    p_botz_id UUID,
    p_session_id TEXT DEFAULT NULL
)
RETURNS BOOLEAN AS $$
DECLARE
    v_botz_skill skill_level;
    v_required_skill skill_level;
    v_current_status work_item_status;
BEGIN
    -- Get BoTZ skill level
    SELECT skill_level INTO v_botz_skill
    FROM botz_instances
    WHERE botz_id = p_botz_id AND is_available = true;

    IF v_botz_skill IS NULL THEN
        RAISE EXCEPTION 'BoTZ instance not found or not available';
    END IF;

    -- Get work item requirements
    SELECT required_skill_level, status INTO v_required_skill, v_current_status
    FROM integration_work_items
    WHERE work_item_id = p_work_item_id
    FOR UPDATE;

    IF v_current_status IS NULL THEN
        RAISE EXCEPTION 'Work item not found';
    END IF;

    IF v_current_status != 'ready' THEN
        RAISE EXCEPTION 'Work item is not ready for claiming (status: %)', v_current_status;
    END IF;

    -- Check skill level (enum comparison)
    IF v_botz_skill::text < v_required_skill::text THEN
        RAISE EXCEPTION 'BoTZ skill level (%) insufficient for work item (requires %)', v_botz_skill, v_required_skill;
    END IF;

    -- Claim the work item
    UPDATE integration_work_items
    SET
        status = 'in_progress',
        assigned_botz_id = p_botz_id,
        assigned_session_id = p_session_id,
        claimed_at = now()
    WHERE work_item_id = p_work_item_id;

    -- Create execution record
    INSERT INTO work_item_executions (work_item_id, botz_id, session_id)
    VALUES (p_work_item_id, p_botz_id, p_session_id);

    RETURN true;
END;
$$ LANGUAGE plpgsql;

-- Function to complete a work item
CREATE OR REPLACE FUNCTION complete_work_item(
    p_work_item_id UUID,
    p_botz_id UUID,
    p_commit_sha TEXT DEFAULT NULL,
    p_pr_url TEXT DEFAULT NULL,
    p_files_modified JSONB DEFAULT '[]',
    p_files_created JSONB DEFAULT '[]'
)
RETURNS BOOLEAN AS $$
BEGIN
    -- Update work item
    UPDATE integration_work_items
    SET
        status = 'completed',
        completed_at = now()
    WHERE work_item_id = p_work_item_id
      AND assigned_botz_id = p_botz_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Work item not found or not assigned to this BoTZ';
    END IF;

    -- Update execution record
    UPDATE work_item_executions
    SET
        status = 'succeeded',
        completed_at = now(),
        duration_seconds = EXTRACT(EPOCH FROM (now() - started_at))::INTEGER,
        commit_sha = p_commit_sha,
        pr_url = p_pr_url,
        files_modified = p_files_modified,
        files_created = p_files_created
    WHERE work_item_id = p_work_item_id
      AND botz_id = p_botz_id
      AND status = 'started';

    RETURN true;
END;
$$ LANGUAGE plpgsql;

-- Function to find available work items for a BoTZ
CREATE OR REPLACE FUNCTION get_available_work_items(
    p_botz_id UUID,
    p_integration_filter TEXT DEFAULT NULL,
    p_limit INTEGER DEFAULT 10
)
RETURNS TABLE (
    work_item_id UUID,
    integration_name TEXT,
    title TEXT,
    description TEXT,
    priority work_item_priority,
    required_skill_level skill_level,
    estimated_complexity TEXT,
    files_to_modify JSONB,
    required_mcp_tools JSONB
) AS $$
DECLARE
    v_botz_skill skill_level;
    v_botz_tools JSONB;
BEGIN
    -- Get BoTZ capabilities
    SELECT bi.skill_level, bi.available_mcp_tools INTO v_botz_skill, v_botz_tools
    FROM botz_instances bi
    WHERE bi.botz_id = p_botz_id AND bi.is_available = true;

    IF v_botz_skill IS NULL THEN
        RAISE EXCEPTION 'BoTZ instance not found or not available';
    END IF;

    RETURN QUERY
    SELECT
        wi.work_item_id,
        wi.integration_name,
        wi.title,
        wi.description,
        wi.priority,
        wi.required_skill_level,
        wi.estimated_complexity,
        wi.files_to_modify,
        wi.required_mcp_tools
    FROM integration_work_items wi
    WHERE wi.status = 'ready'
      AND wi.required_skill_level::text <= v_botz_skill::text
      AND (p_integration_filter IS NULL OR wi.integration_name = p_integration_filter)
    ORDER BY
        wi.priority,
        wi.created_at
    LIMIT p_limit;
END;
$$ LANGUAGE plpgsql;

-- View for active work items
CREATE OR REPLACE VIEW active_work_items AS
SELECT
    wi.*,
    bi.botz_name,
    bi.runner_host,
    bi.skill_level AS botz_skill_level
FROM integration_work_items wi
LEFT JOIN botz_instances bi ON wi.assigned_botz_id = bi.botz_id
WHERE wi.status IN ('ready', 'in_progress');

-- View for BoTZ stats
CREATE OR REPLACE VIEW botz_stats AS
SELECT
    bi.botz_id,
    bi.botz_name,
    bi.skill_level,
    bi.runner_host,
    bi.is_available,
    COUNT(CASE WHEN wi.status = 'in_progress' THEN 1 END) AS active_items,
    COUNT(CASE WHEN wi.status = 'completed' THEN 1 END) AS completed_items,
    MAX(wie.completed_at) AS last_completion
FROM botz_instances bi
LEFT JOIN integration_work_items wi ON bi.botz_id = wi.assigned_botz_id
LEFT JOIN work_item_executions wie ON bi.botz_id = wie.botz_id AND wie.status = 'succeeded'
GROUP BY bi.botz_id, bi.botz_name, bi.skill_level, bi.runner_host, bi.is_available;

-- RLS Policies
ALTER TABLE botz_instances ENABLE ROW LEVEL SECURITY;
ALTER TABLE integration_work_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE work_item_executions ENABLE ROW LEVEL SECURITY;

-- Service role has full access
CREATE POLICY botz_service_policy ON botz_instances
    FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE POLICY work_items_service_policy ON integration_work_items
    FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE POLICY executions_service_policy ON work_item_executions
    FOR ALL TO service_role USING (true) WITH CHECK (true);

-- Authenticated users can read all, but only modify their own BoTZ
CREATE POLICY botz_read_policy ON botz_instances
    FOR SELECT TO authenticated USING (true);

CREATE POLICY work_items_read_policy ON integration_work_items
    FOR SELECT TO authenticated USING (true);

CREATE POLICY executions_read_policy ON work_item_executions
    FOR SELECT TO authenticated USING (true);

-- Comments for documentation
COMMENT ON TABLE botz_instances IS 'Registry of PMOVES-BoTZ CLI instances with their capabilities';
COMMENT ON TABLE integration_work_items IS 'Work items per integration that BoTZ CLIs can claim and execute';
COMMENT ON TABLE work_item_executions IS 'Execution history for work items';
COMMENT ON FUNCTION claim_work_item IS 'Atomically claim a work item for a BoTZ instance';
COMMENT ON FUNCTION complete_work_item IS 'Mark a work item as completed';
COMMENT ON FUNCTION get_available_work_items IS 'Get work items available for a BoTZ based on skill level';
