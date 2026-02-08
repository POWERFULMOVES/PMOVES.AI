-- Agent Threads Table for Long Thread (Z) Persistence
-- Stores thread execution state for Agent Zero checkpoint/recovery

-- Create the agent_threads table
CREATE TABLE IF NOT EXISTS pmoves_core.agent_threads (
    id TEXT PRIMARY KEY,
    thread_id TEXT NOT NULL,
    thread_type TEXT NOT NULL,
    state JSONB NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'pending',
    iteration INTEGER NOT NULL DEFAULT 0,
    total_iterations INTEGER,
    progress FLOAT NOT NULL DEFAULT 0.0,
    error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Add comments
COMMENT ON TABLE pmoves_core.agent_threads IS
    'Thread execution state for Agent Zero long-running tasks with checkpoint/recovery';

COMMENT ON COLUMN pmoves_core.agent_threads.id IS
    'Unique checkpoint identifier (thread_id + timestamp)';

COMMENT ON COLUMN pmoves_core.agent_threads.thread_id IS
    'Thread identifier (matches thread_id from gateway/threads.py)';

COMMENT ON COLUMN pmoves_core.agent_threads.thread_type IS
    'Thread type: base, parallel, chained, fusion, big, long';

COMMENT ON COLUMN pmoves_core.agent_threads.state IS
    'JSONB serialized thread state for checkpoint recovery';

COMMENT ON COLUMN pmoves_core.agent_threads.status IS
    'Thread status: pending, running, completed, failed, cancelled';

COMMENT ON COLUMN pmoves_core.agent_threads.iteration IS
    'Current iteration number for long-running threads';

COMMENT ON COLUMN pmoves_core.agent_threads.total_iterations IS
    'Total iterations (if known in advance)';

COMMENT ON COLUMN pmoves_core.agent_threads.progress IS
    'Thread progress from 0.0 to 1.0';

COMMENT ON COLUMN pmoves_core.agent_threads.error IS
    'Error message if thread failed';

-- Create indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_agent_threads_thread_id
    ON pmoves_core.agent_threads(thread_id);

CREATE INDEX IF NOT EXISTS idx_agent_threads_status
    ON pmoves_core.agent_threads(status);

CREATE INDEX IF NOT EXISTS idx_agent_threads_updated_at
    ON pmoves_core.agent_threads(updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_agent_threads_thread_type
    ON pmoves_core.agent_threads(thread_type);

-- Create updated_at trigger
CREATE OR REPLACE FUNCTION pmoves_core.update_agent_threads_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_update_agent_threads_updated_at
    ON pmoves_core.agent_threads;

CREATE TRIGGER trigger_update_agent_threads_updated_at
    BEFORE UPDATE ON pmoves_core.agent_threads
    FOR EACH ROW
    EXECUTE FUNCTION pmoves_core.update_agent_threads_updated_at();

-- Enable Row Level Security
ALTER TABLE pmoves_core.agent_threads ENABLE ROW LEVEL SECURITY;

-- Drop existing policies if any
DROP POLICY IF EXISTS agent_threads_select ON pmoves_core.agent_threads;
DROP POLICY IF EXISTS agent_threads_insert ON pmoves_core.agent_threads;
DROP POLICY IF EXISTS agent_threads_update ON pmoves_core.agent_threads;
DROP POLICY IF EXISTS agent_threads_delete ON pmoves_core.agent_threads;
DROP POLICY IF EXISTS agent_threads_all ON pmoves_core.agent_threads;

-- Create policies for local development (permissive)
-- NOTE: Review and restrict for production deployment
CREATE POLICY agent_threads_select ON pmoves_core.agent_threads
    FOR SELECT USING (true);

CREATE POLICY agent_threads_insert ON pmoves_core.agent_threads
    FOR INSERT WITH CHECK (true);

CREATE POLICY agent_threads_update ON pmoves_core.agent_threads
    FOR UPDATE USING (true);

CREATE POLICY agent_threads_delete ON pmoves_core.agent_threads
    FOR DELETE USING (true);

-- Grant permissions
GRANT SELECT, INSERT, UPDATE, DELETE ON pmoves_core.agent_threads TO anon;
GRANT SELECT, INSERT, UPDATE, DELETE ON pmoves_core.agent_threads TO authenticated;
GRANT ALL ON pmoves_core.agent_threads TO service_role;

-- Grant usage on sequences (if any)
-- GRANT USAGE ON ALL SEQUENCES IN SCHEMA pmoves_core TO anon, authenticated, service_role;
