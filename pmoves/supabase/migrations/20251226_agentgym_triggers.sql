-- AgentGym RL Training Triggers
-- Migration: 20251226_agentgym_triggers.sql
-- Purpose: Add temporal consistency triggers for training timestamps
-- Service: AgentGym RL Coordinator (port 8114)

-- ============================================================================
-- Trigger: Auto-set started_at when status changes to "running"
-- ============================================================================

CREATE OR REPLACE FUNCTION agentgym_set_training_timestamps()
RETURNS TRIGGER AS $$
BEGIN
    -- Set started_at when transitioning to "running"
    IF NEW.status = 'running' AND (OLD.status IS NULL OR OLD.status != 'running') THEN
        IF NEW.started_at IS NULL THEN
            NEW.started_at = NOW();
        END IF;
    END IF;

    -- Set completed_at when transitioning to terminal state
    IF NEW.status IN ('completed', 'failed', 'cancelled') THEN
        IF (OLD.status IS NULL OR OLD.status NOT IN ('completed', 'failed', 'cancelled')) THEN
            IF NEW.completed_at IS NULL THEN
                NEW.completed_at = NOW();
            END IF;
        END IF;
    END IF;

    -- Clear completed_at if transitioning back to non-terminal state (re-run)
    IF NEW.status NOT IN ('completed', 'failed', 'cancelled') THEN
        NEW.completed_at := NULL;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION agentgym_set_training_timestamps IS
    'Automatically set training timestamps based on status transitions';

DROP TRIGGER IF EXISTS trg_agentgym_training_timestamps ON public.agentgym_training_runs;
CREATE TRIGGER trg_agentgym_training_timestamps
    BEFORE UPDATE ON public.agentgym_training_runs
    FOR EACH ROW
    WHEN (NEW.status IS DISTINCT FROM OLD.status OR NEW.started_at IS DISTINCT FROM OLD.started_at OR NEW.completed_at IS DISTINCT FROM OLD.completed_at)
    EXECUTE FUNCTION agentgym_set_training_timestamps();

-- ============================================================================
-- Trigger: Auto-update updated_at timestamp on voice_persona
-- ============================================================================

CREATE OR REPLACE FUNCTION voice_persona_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_voice_persona_updated_at ON public.voice_persona;
CREATE TRIGGER trg_voice_persona_updated_at
    BEFORE UPDATE ON public.voice_persona
    FOR EACH ROW
    EXECUTE FUNCTION voice_persona_updated_at();

-- ============================================================================
-- Trigger: Set training_started_at when voice_cloning_status changes to "training"
-- ============================================================================

CREATE OR REPLACE FUNCTION voice_cloning_set_training_timestamps()
RETURNS TRIGGER AS $$
BEGIN
    -- Set training_started_at when transitioning to "training"
    IF NEW.voice_cloning_status = 'training' THEN
        IF (OLD.voice_cloning_status IS NULL OR OLD.voice_cloning_status != 'training') THEN
            IF NEW.training_started_at IS NULL THEN
                NEW.training_started_at = NOW();
            END IF;
        END IF;
    END IF;

    -- Set training_completed_at when transitioning to terminal state
    IF NEW.voice_cloning_status IN ('completed', 'failed') THEN
        IF (OLD.voice_cloning_status IS NULL OR OLD.voice_cloning_status NOT IN ('completed', 'failed')) THEN
            IF NEW.training_completed_at IS NULL THEN
                NEW.training_completed_at = NOW();
            END IF;
        END IF;
    END IF;

    -- Clear terminal timestamps if transitioning back to "pending" (re-queue)
    IF NEW.voice_cloning_status = 'pending' THEN
        NEW.training_started_at := NULL;
        NEW.training_completed_at := NULL;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION voice_cloning_set_training_timestamps IS
    'Automatically set voice cloning training timestamps based on status transitions';

DROP TRIGGER IF EXISTS trg_voice_cloning_timestamps ON public.voice_persona;
CREATE TRIGGER trg_voice_cloning_timestamps
    BEFORE UPDATE ON public.voice_persona
    FOR EACH ROW
    WHEN (NEW.voice_cloning_status IS DISTINCT FROM OLD.voice_cloning_status)
    EXECUTE FUNCTION voice_cloning_set_training_timestamps();
