-- Voice Cloning State Transitions
-- Migration: 20251226_state_transitions.sql
-- Purpose: Add state transition validation for voice cloning training
-- Service: Flute Gateway (ports 8055/8056)

-- ============================================================================
-- Function: Validate voice cloning status transitions
-- ============================================================================

CREATE OR REPLACE FUNCTION validate_voice_cloning_status_transition()
RETURNS TRIGGER AS $$
DECLARE
    valid_transition BOOLEAN := FALSE;
BEGIN
    -- Allow setting status on new rows
    IF TG_OP = 'INSERT' THEN
        RETURN NEW;
    END IF;

    -- No transition occurred
    IF NEW.voice_cloning_status IS NOT DISTINCT FROM OLD.voice_cloning_status THEN
        RETURN NEW;
    END IF;

    -- Valid transitions:
    -- pending -> training (start training)
    -- training -> completed (success)
    -- training -> failed (error)
    -- completed -> training (re-train)
    -- failed -> pending (retry)
    -- failed -> training (retry immediately)
    -- pending -> pending (no-op, already handled above)
    -- training -> training (no-op, already handled above)
    -- completed -> completed (no-op, already handled above)
    -- failed -> failed (no-op, already handled above)

    CASE
        -- Starting training
        WHEN OLD.voice_cloning_status = 'pending' AND NEW.voice_cloning_status = 'training' THEN
            valid_transition := TRUE;

        -- Successful completion
        WHEN OLD.voice_cloning_status = 'training' AND NEW.voice_cloning_status = 'completed' THEN
            valid_transition := TRUE;

        -- Training failed
        WHEN OLD.voice_cloning_status = 'training' AND NEW.voice_cloning_status = 'failed' THEN
            valid_transition := TRUE;

        -- Re-training from completed state
        WHEN OLD.voice_cloning_status = 'completed' AND NEW.voice_cloning_status = 'training' THEN
            valid_transition := TRUE;

        -- Retry from failed state
        WHEN OLD.voice_cloning_status = 'failed' AND NEW.voice_cloning_status IN ('pending', 'training') THEN
            valid_transition := TRUE;

        -- Reset from completed back to pending (manual reset)
        WHEN OLD.voice_cloning_status = 'completed' AND NEW.voice_cloning_status = 'pending' THEN
            valid_transition := TRUE;

        ELSE
            valid_transition := FALSE;
    END CASE;

    IF NOT valid_transition THEN
        RAISE EXCEPTION 'Invalid voice_cloning_status transition: %s -> %s',
            OLD.voice_cloning_status, NEW.voice_cloning_status
        USING ERRCODE = 'restrict_violation';
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION validate_voice_cloning_status_transition IS
    'Validates that voice cloning status follows allowed state transitions';

DROP TRIGGER IF EXISTS trg_voice_cloning_status_transition ON public.voice_persona;
CREATE TRIGGER trg_voice_cloning_status_transition
    BEFORE UPDATE ON public.voice_persona
    FOR EACH ROW
    WHEN (NEW.voice_cloning_status IS DISTINCT FROM OLD.voice_cloning_status)
    EXECUTE FUNCTION validate_voice_cloning_status_transition();

-- ============================================================================
-- Function: Validate AgentGym training run status transitions
-- ============================================================================

CREATE OR REPLACE FUNCTION validate_agentgym_training_status_transition()
RETURNS TRIGGER AS $$
DECLARE
    valid_transition BOOLEAN := FALSE;
BEGIN
    -- Allow setting status on new rows
    IF TG_OP = 'INSERT' THEN
        RETURN NEW;
    END IF;

    -- No transition occurred
    IF NEW.status IS NOT DISTINCT FROM OLD.status THEN
        RETURN NEW;
    END IF;

    -- Valid transitions for training runs:
    -- pending -> running (start training)
    -- running -> completed (success)
    -- running -> failed (error)
    -- running -> cancelled (user cancelled)
    -- pending -> cancelled (cancelled before starting)
    -- failed -> pending (retry)
    -- failed -> running (retry immediately)

    CASE
        -- Starting training
        WHEN OLD.status = 'pending' AND NEW.status = 'running' THEN
            valid_transition := TRUE;

        -- Cancel before start
        WHEN OLD.status = 'pending' AND NEW.status = 'cancelled' THEN
            valid_transition := TRUE;

        -- Successful completion
        WHEN OLD.status = 'running' AND NEW.status = 'completed' THEN
            valid_transition := TRUE;

        -- Training failed
        WHEN OLD.status = 'running' AND NEW.status = 'failed' THEN
            valid_transition := TRUE;

        -- Training cancelled
        WHEN OLD.status = 'running' AND NEW.status = 'cancelled' THEN
            valid_transition := TRUE;

        -- Retry from failed state
        WHEN OLD.status = 'failed' AND NEW.status IN ('pending', 'running') THEN
            valid_transition := TRUE;

        ELSE
            valid_transition := FALSE;
    END CASE;

    IF NOT valid_transition THEN
        RAISE EXCEPTION 'Invalid agentgym training status transition: %s -> %s',
            OLD.status, NEW.status
        USING ERRCODE = 'restrict_violation';
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION validate_agentgym_training_status_transition IS
    'Validates that AgentGym training status follows allowed state transitions';

DROP TRIGGER IF EXISTS trg_agentgym_training_status_transition ON public.agentgym_training_runs;
CREATE TRIGGER trg_agentgym_training_status_transition
    BEFORE UPDATE ON public.agentgym_training_runs
    FOR EACH ROW
    WHEN (NEW.status IS DISTINCT FROM OLD.status)
    EXECUTE FUNCTION validate_agentgym_training_status_transition();
