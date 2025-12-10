-- Unified ingestion queue for all content types
-- Phase 9: Ingestion Control & Agent Chat

-- Create enum for ingestion status
DO $$ BEGIN
  CREATE TYPE ingestion_status AS ENUM (
    'pending',      -- Awaiting user approval
    'approved',     -- User approved, queued for processing
    'rejected',     -- User rejected
    'processing',   -- Currently being processed
    'completed',    -- Successfully processed
    'failed'        -- Processing failed
  );
EXCEPTION
  WHEN duplicate_object THEN NULL;
END $$;

-- Create enum for source types
DO $$ BEGIN
  CREATE TYPE ingestion_source_type AS ENUM (
    'youtube',      -- YouTube video
    'pdf',          -- PDF document
    'url',          -- Web URL
    'upload',       -- Direct file upload
    'notebook',     -- Open Notebook import
    'discord',      -- Discord message/attachment
    'telegram',     -- Telegram message/attachment
    'rss'           -- RSS feed item
  );
EXCEPTION
  WHEN duplicate_object THEN NULL;
END $$;

-- Unified ingestion queue table
CREATE TABLE IF NOT EXISTS public.ingestion_queue (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  owner_id uuid REFERENCES auth.users(id),

  -- Source identification
  source_type ingestion_source_type NOT NULL,
  source_url text,
  source_id text,                    -- External ID (YouTube video ID, etc.)

  -- Display info
  title text,
  description text,
  thumbnail_url text,
  duration_seconds int,

  -- Metadata from source
  source_meta jsonb DEFAULT '{}'::jsonb,

  -- Processing state
  status ingestion_status DEFAULT 'pending',
  priority int DEFAULT 0,            -- Higher = more important

  -- Approval tracking
  approved_by uuid REFERENCES auth.users(id),
  approved_at timestamptz,
  rejection_reason text,

  -- Processing tracking
  processor_id text,                 -- Service handling this item
  processing_started_at timestamptz,
  processed_at timestamptz,
  error_message text,
  retry_count int DEFAULT 0,

  -- Output references
  output_refs jsonb DEFAULT '{}'::jsonb,  -- MinIO paths, Supabase IDs, etc.

  -- Timestamps
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now(),

  -- Constraints
  CONSTRAINT valid_source CHECK (
    source_url IS NOT NULL OR source_id IS NOT NULL
  )
);

-- Enable RLS
ALTER TABLE public.ingestion_queue ENABLE ROW LEVEL SECURITY;

-- RLS Policies
DO $$
BEGIN
  -- Service role full access
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname = 'public'
    AND tablename = 'ingestion_queue'
    AND policyname = 'ingestion_service_all'
  ) THEN
    CREATE POLICY ingestion_service_all ON public.ingestion_queue
      FOR ALL USING (auth.role() = 'service_role');
  END IF;

  -- Owner read access
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname = 'public'
    AND tablename = 'ingestion_queue'
    AND policyname = 'ingestion_owner_read'
  ) THEN
    CREATE POLICY ingestion_owner_read ON public.ingestion_queue
      FOR SELECT USING (auth.uid() = owner_id);
  END IF;

  -- Owner can update status (approve/reject)
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname = 'public'
    AND tablename = 'ingestion_queue'
    AND policyname = 'ingestion_owner_update'
  ) THEN
    CREATE POLICY ingestion_owner_update ON public.ingestion_queue
      FOR UPDATE USING (auth.uid() = owner_id);
  END IF;
END $$;

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_ingestion_queue_status
  ON public.ingestion_queue(status, priority DESC, created_at ASC);

CREATE INDEX IF NOT EXISTS idx_ingestion_queue_owner
  ON public.ingestion_queue(owner_id, status, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_ingestion_queue_source_type
  ON public.ingestion_queue(source_type, status);

CREATE INDEX IF NOT EXISTS idx_ingestion_queue_source_id
  ON public.ingestion_queue(source_id) WHERE source_id IS NOT NULL;

-- Enable Realtime
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_publication_tables
    WHERE pubname = 'supabase_realtime'
    AND schemaname = 'public'
    AND tablename = 'ingestion_queue'
  ) THEN
    ALTER PUBLICATION supabase_realtime ADD TABLE public.ingestion_queue;
  END IF;
END $$;

-- Updated_at trigger
CREATE OR REPLACE FUNCTION update_ingestion_queue_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS ingestion_queue_updated_at ON public.ingestion_queue;
CREATE TRIGGER ingestion_queue_updated_at
  BEFORE UPDATE ON public.ingestion_queue
  FOR EACH ROW EXECUTE FUNCTION update_ingestion_queue_updated_at();

-- View for pending items with thumbnails
CREATE OR REPLACE VIEW public.ingestion_queue_pending AS
SELECT
  id,
  source_type,
  source_url,
  source_id,
  title,
  description,
  thumbnail_url,
  duration_seconds,
  priority,
  created_at,
  source_meta->>'channel_name' as channel_name,
  source_meta->>'uploader' as uploader
FROM public.ingestion_queue
WHERE status = 'pending'
ORDER BY priority DESC, created_at ASC;

-- Function to approve an ingestion item
CREATE OR REPLACE FUNCTION approve_ingestion(
  p_id uuid,
  p_priority int DEFAULT NULL
) RETURNS public.ingestion_queue
LANGUAGE plpgsql SECURITY DEFINER AS $$
DECLARE
  v_result public.ingestion_queue;
BEGIN
  UPDATE public.ingestion_queue
  SET
    status = 'approved',
    approved_by = auth.uid(),
    approved_at = now(),
    priority = COALESCE(p_priority, priority)
  WHERE id = p_id
    AND status = 'pending'
    AND (auth.role() = 'service_role' OR owner_id = auth.uid())
  RETURNING * INTO v_result;

  RETURN v_result;
END;
$$;

-- Function to reject an ingestion item
CREATE OR REPLACE FUNCTION reject_ingestion(
  p_id uuid,
  p_reason text DEFAULT NULL
) RETURNS public.ingestion_queue
LANGUAGE plpgsql SECURITY DEFINER AS $$
DECLARE
  v_result public.ingestion_queue;
BEGIN
  UPDATE public.ingestion_queue
  SET
    status = 'rejected',
    rejection_reason = p_reason,
    approved_by = auth.uid(),
    approved_at = now()
  WHERE id = p_id
    AND status = 'pending'
    AND (auth.role() = 'service_role' OR owner_id = auth.uid())
  RETURNING * INTO v_result;

  RETURN v_result;
END;
$$;

-- Function to get queue stats
CREATE OR REPLACE FUNCTION get_ingestion_stats()
RETURNS TABLE (
  status ingestion_status,
  source_type ingestion_source_type,
  count bigint
)
LANGUAGE sql STABLE SECURITY DEFINER AS $$
  SELECT status, source_type, COUNT(*)
  FROM public.ingestion_queue
  WHERE owner_id = auth.uid() OR auth.role() = 'service_role'
  GROUP BY status, source_type
  ORDER BY status, source_type;
$$;

-- Grant permissions
GRANT EXECUTE ON FUNCTION approve_ingestion TO authenticated;
GRANT EXECUTE ON FUNCTION approve_ingestion TO service_role;
GRANT EXECUTE ON FUNCTION reject_ingestion TO authenticated;
GRANT EXECUTE ON FUNCTION reject_ingestion TO service_role;
GRANT EXECUTE ON FUNCTION get_ingestion_stats TO authenticated;
GRANT EXECUTE ON FUNCTION get_ingestion_stats TO service_role;
GRANT SELECT ON public.ingestion_queue_pending TO authenticated;
GRANT SELECT ON public.ingestion_queue_pending TO service_role;

COMMENT ON TABLE public.ingestion_queue IS 'Unified queue for all content types awaiting ingestion approval';
COMMENT ON VIEW public.ingestion_queue_pending IS 'Pending ingestion items with display-friendly fields';
