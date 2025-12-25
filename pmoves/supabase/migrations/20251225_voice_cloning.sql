-- Voice Cloning Extension
-- Migration: 20251225_voice_cloning.sql
-- Purpose: Add voice cloning capabilities to voice_persona table
-- Service: Flute Gateway (ports 8055/8056)

-- ============================================================================
-- Add voice cloning columns to voice_persona table
-- ============================================================================

-- Voice cloning training status (NULL = not registered for training)
ALTER TABLE public.voice_persona
ADD COLUMN IF NOT EXISTS voice_cloning_status text
CHECK (voice_cloning_status IN ('pending', 'training', 'completed', 'failed'));

-- RVC model file URI (stored in MinIO: minio://voice-models/{slug}.pth)
ALTER TABLE public.voice_persona
ADD COLUMN IF NOT EXISTS rvc_model_uri text;

-- RVC index file URI (stored in MinIO: minio://voice-models/{slug}.index)
ALTER TABLE public.voice_persona
ADD COLUMN IF NOT EXISTS rvc_index_uri text;

-- Training progress (0-100)
ALTER TABLE public.voice_persona
ADD COLUMN IF NOT EXISTS training_progress int
DEFAULT 0
CHECK (training_progress >= 0 AND training_progress <= 100);

-- Training/error message
ALTER TABLE public.voice_persona
ADD COLUMN IF NOT EXISTS training_message text;

-- Timestamps
ALTER TABLE public.voice_persona
ADD COLUMN IF NOT EXISTS training_started_at timestamptz;
ALTER TABLE public.voice_persona
ADD COLUMN IF NOT EXISTS training_completed_at timestamptz;

-- ============================================================================
-- Add completion validation constraint
-- ============================================================================

-- Ensure completed training has model URIs set
ALTER TABLE public.voice_persona
ADD CONSTRAINT voice_persona_completion_check
CHECK (
    voice_cloning_status IS DISTINCT FROM 'completed'
    OR (rvc_model_uri IS NOT NULL AND rvc_index_uri IS NOT NULL)
);

-- ============================================================================
-- Indexes for voice cloning queries
-- ============================================================================

-- Find personas ready for training
CREATE INDEX IF NOT EXISTS idx_voice_persona_cloning_pending
    ON public.voice_persona(voice_cloning_status)
    WHERE voice_cloning_status IN ('pending', 'training');

-- Find completed voice clones
CREATE INDEX IF NOT EXISTS idx_voice_persona_cloning_completed
    ON public.voice_persona(voice_cloning_status)
    WHERE voice_cloning_status = 'completed';

-- ============================================================================
-- Comments
-- ============================================================================

COMMENT ON COLUMN public.voice_persona.voice_cloning_status IS
    'Voice cloning training status: pending → training → completed/failed';

COMMENT ON COLUMN public.voice_persona.rvc_model_uri IS
    'MinIO URI for trained RVC .pth file: minio://voice-models/{slug}.pth';

COMMENT ON COLUMN public.voice_persona.rvc_index_uri IS
    'MinIO URI for RVC .index file: minio://voice-models/{slug}.index';

COMMENT ON COLUMN public.voice_persona.training_progress IS
    'Training progress percentage (0-100)';

COMMENT ON COLUMN public.voice_persona.training_message IS
    'Status message or error details from training process';

-- ============================================================================
-- Function: Register voice for cloning
-- ============================================================================

CREATE OR REPLACE FUNCTION register_voice_cloning(
    p_persona_slug text,
    p_sample_uri text
)
RETURNS uuid AS $$
DECLARE
    v_persona_id uuid;
BEGIN
    -- Get persona ID
    SELECT id INTO v_persona_id
    FROM public.voice_persona
    WHERE slug = p_persona_slug AND is_active = true;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Voice persona not found: %', p_persona_slug;
    END IF;

    -- Update for cloning
    UPDATE public.voice_persona
    SET
        voice_sample_uri = p_sample_uri,
        voice_cloning_status = 'pending',
        training_progress = 0,
        training_message = 'Queued for training',
        training_started_at = NULL,
        training_completed_at = NULL
    WHERE id = v_persona_id;

    RETURN v_persona_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

COMMENT ON FUNCTION register_voice_cloning IS
    'Register a voice sample for cloning training';

-- ============================================================================
-- Function: Update training status
-- ============================================================================

CREATE OR REPLACE FUNCTION update_voice_cloning_status(
    p_persona_id uuid,
    p_status text,
    p_progress int DEFAULT NULL,
    p_message text DEFAULT NULL,
    p_model_uri text DEFAULT NULL,
    p_index_uri text DEFAULT NULL
)
RETURNS boolean AS $$
BEGIN
    UPDATE public.voice_persona
    SET
        voice_cloning_status = p_status,
        training_progress = COALESCE(p_progress, training_progress),
        training_message = COALESCE(p_message, training_message),
        rvc_model_uri = COALESCE(p_model_uri, rvc_model_uri),
        rvc_index_uri = COALESCE(p_index_uri, rvc_index_uri),
        training_started_at = CASE
            WHEN p_status = 'training' AND training_started_at IS NULL
            THEN NOW()
            ELSE training_started_at
        END,
        training_completed_at = CASE
            WHEN p_status IN ('completed', 'failed') AND training_completed_at IS NULL
            THEN NOW()
            ELSE training_completed_at
        END
    WHERE id = p_persona_id;

    RETURN FOUND;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

COMMENT ON FUNCTION update_voice_cloning_status IS
    'Update voice cloning training status and progress';

-- ============================================================================
-- Grant execute permissions
-- ============================================================================

-- Voice cloning registration is service-only (requires service role for security)
GRANT EXECUTE ON FUNCTION register_voice_cloning(text, text) TO service_role;

-- Training status updates are service-only (GPU service callback)
GRANT EXECUTE ON FUNCTION update_voice_cloning_status(uuid, text, int, text, text, text) TO service_role;

-- ============================================================================
-- Trigger: Enable realtime for voice cloning status updates
-- ============================================================================

ALTER PUBLICATION supabase_realtime ADD TABLE public.voice_persona;
