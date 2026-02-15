-- AgentGym RL Training Tables
-- Migration: 20251225_agentgym_rl.sql
-- Purpose: Add reinforcement learning trajectory and training tracking for AgentGym
-- Service: AgentGym RL Coordinator (port 8114)

-- ============================================================================
-- Table: agentgym_trajectories
-- Purpose: Store trajectory data collected from NATS geometry events
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.agentgym_trajectories (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id uuid NOT NULL,
    trajectory_data jsonb NOT NULL,
    event_count int NOT NULL DEFAULT 0,

    -- Metadata
    task_type text,
    environment text,
    agent_id uuid REFERENCES pmoves_core.agent(id),

    -- Publishing
    published_to_hf boolean DEFAULT false,
    hf_dataset_id text,
    hf_repo_url text,

    -- Timestamps
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now(),

    -- Constraints
    CONSTRAINT agentgym_trajectories_event_count_check CHECK (event_count >= 0),
    CONSTRAINT agentgym_trajectories_publishing_check CHECK (
        published_to_hf = false OR hf_dataset_id IS NOT NULL
    )
);

-- Indexes
CREATE UNIQUE INDEX IF NOT EXISTS idx_agentgym_trajectories_session_unique
    ON public.agentgym_trajectories(session_id);

CREATE INDEX IF NOT EXISTS idx_agentgym_trajectories_agent
    ON public.agentgym_trajectories(agent_id) WHERE agent_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_agentgym_trajectories_published
    ON public.agentgym_trajectories(published_to_hf) WHERE published_to_hf = false;

CREATE INDEX IF NOT EXISTS idx_agentgym_trajectories_task_type
    ON public.agentgym_trajectories(task_type);

-- ============================================================================
-- Table: agentgym_training_runs
-- Purpose: Track PPO training run status and results
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.agentgym_training_runs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id text UNIQUE NOT NULL,
    config jsonb NOT NULL,

    -- Status
    status text NOT NULL DEFAULT 'pending' CHECK (status IN (
        'pending', 'running', 'completed', 'failed', 'cancelled'
    )),

    -- Progress tracking
    current_epoch int DEFAULT 0,
    total_epochs int,
    checkpoint_path text,

    -- Metrics
    final_reward float,
    mean_reward float,
    std_reward float,

    -- Timestamps
    started_at timestamptz,
    completed_at timestamptz,
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now(),

    -- Error tracking
    error_message text,
    exit_code int,

    -- Constraints
    CONSTRAINT agentgym_training_runs_epoch_bounds_check CHECK (
        current_epoch <= total_epochs OR total_epochs IS NULL
    )
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_agentgym_training_runs_status
    ON public.agentgym_training_runs(status);

CREATE INDEX IF NOT EXISTS idx_agentgym_training_runs_run_id
    ON public.agentgym_training_runs(run_id);

CREATE INDEX IF NOT EXISTS idx_agentgym_training_runs_started
    ON public.agentgym_training_runs(started_at DESC);

-- ============================================================================
-- Comments
-- ============================================================================

COMMENT ON TABLE public.agentgym_trajectories IS
    'RL trajectory data collected from NATS geometry events for AgentGym training';

COMMENT ON TABLE public.agentgym_training_runs IS
    'PPO training run tracking for AgentGym RL coordinator';

COMMENT ON COLUMN public.agentgym_trajectories.trajectory_data IS
    'JSON trajectory data including observations, actions, rewards';

COMMENT ON COLUMN public.agentgym_training_runs.config IS
    'PPO training configuration (OmegaConf format)';

-- ============================================================================
-- Trigger: Auto-update updated_at timestamps
-- ============================================================================

CREATE OR REPLACE FUNCTION update_agentgym_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_agentgym_trajectories_updated ON public.agentgym_trajectories;
CREATE TRIGGER trg_agentgym_trajectories_updated
    BEFORE UPDATE ON public.agentgym_trajectories
    FOR EACH ROW EXECUTE FUNCTION update_agentgym_updated_at();

DROP TRIGGER IF EXISTS trg_agentgym_training_runs_updated ON public.agentgym_training_runs;
CREATE TRIGGER trg_agentgym_training_runs_updated
    BEFORE UPDATE ON public.agentgym_training_runs
    FOR EACH ROW EXECUTE FUNCTION update_agentgym_updated_at();

-- ============================================================================
-- Function: Create or update trajectory
-- ============================================================================

CREATE OR REPLACE FUNCTION upsert_trajectory(
    p_session_id uuid,
    p_trajectory_data jsonb,
    p_event_count int DEFAULT 1,
    p_task_type text DEFAULT NULL,
    p_environment text DEFAULT NULL,
    p_agent_id uuid DEFAULT NULL
)
RETURNS uuid AS $$
DECLARE
    v_trajectory_id uuid;
BEGIN
    INSERT INTO public.agentgym_trajectories (
        session_id,
        trajectory_data,
        event_count,
        task_type,
        environment,
        agent_id
    ) VALUES (
        p_session_id,
        p_trajectory_data,
        p_event_count,
        p_task_type,
        p_environment,
        p_agent_id
    )
    ON CONFLICT (session_id) DO UPDATE SET
        trajectory_data = agentgym_trajectories.trajectory_data || p_trajectory_data,
        event_count = agentgym_trajectories.event_count + p_event_count,
        updated_at = NOW()
    RETURNING id INTO v_trajectory_id;

    RETURN v_trajectory_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

COMMENT ON FUNCTION upsert_trajectory IS
    'Create or update trajectory data for a session';

-- ============================================================================
-- Function: Create training run
-- ============================================================================

CREATE OR REPLACE FUNCTION create_training_run(
    p_run_id text,
    p_config jsonb,
    p_total_epochs int DEFAULT 100
)
RETURNS uuid AS $$
DECLARE
    v_run_uuid uuid;
BEGIN
    INSERT INTO public.agentgym_training_runs (
        run_id,
        config,
        total_epochs,
        status
    ) VALUES (
        p_run_id,
        p_config,
        p_total_epochs,
        'pending'
    ) RETURNING id INTO v_run_uuid;

    RETURN v_run_uuid;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

COMMENT ON FUNCTION create_training_run IS
    'Create a new PPO training run';

-- ============================================================================
-- Function: Update training run status
-- ============================================================================

CREATE OR REPLACE FUNCTION update_training_run_status(
    p_run_id text,
    p_status text,
    p_current_epoch int DEFAULT NULL,
    p_checkpoint_path text DEFAULT NULL,
    p_mean_reward float DEFAULT NULL,
    p_error_message text DEFAULT NULL,
    p_exit_code int DEFAULT NULL
)
RETURNS boolean AS $$
BEGIN
    UPDATE public.agentgym_training_runs
    SET
        status = p_status,
        current_epoch = COALESCE(p_current_epoch, current_epoch),
        checkpoint_path = COALESCE(p_checkpoint_path, checkpoint_path),
        mean_reward = COALESCE(p_mean_reward, mean_reward),
        error_message = COALESCE(p_error_message, error_message),
        exit_code = COALESCE(p_exit_code, exit_code),
        started_at = CASE
            WHEN p_status = 'running' AND started_at IS NULL
            THEN NOW()
            ELSE started_at
        END,
        completed_at = CASE
            WHEN p_status IN ('completed', 'failed', 'cancelled') AND completed_at IS NULL
            THEN NOW()
            ELSE completed_at
        END,
        updated_at = NOW()
    WHERE run_id = p_run_id;

    RETURN FOUND;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

COMMENT ON FUNCTION update_training_run_status IS
    'Update training run status and progress';

-- ============================================================================
-- Grant permissions
-- ============================================================================

GRANT EXECUTE ON FUNCTION upsert_trajectory TO service_role;
GRANT EXECUTE ON FUNCTION create_training_run TO service_role;
GRANT EXECUTE ON FUNCTION update_training_run_status TO service_role;

-- ============================================================================
-- Enable RLS
-- ============================================================================

ALTER TABLE public.agentgym_trajectories ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.agentgym_training_runs ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS agentgym_trajectories_service_role ON public.agentgym_trajectories;
CREATE POLICY agentgym_trajectories_service_role
    ON public.agentgym_trajectories
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

DROP POLICY IF EXISTS agentgym_training_runs_service_role ON public.agentgym_training_runs;
CREATE POLICY agentgym_training_runs_service_role
    ON public.agentgym_training_runs
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- ============================================================================
-- Enable realtime
-- ============================================================================

ALTER PUBLICATION supabase_realtime ADD TABLE public.agentgym_training_runs;
ALTER PUBLICATION supabase_realtime ADD TABLE public.agentgym_trajectories;
