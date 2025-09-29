-- Publisher audit trail for content publishing pipeline
-- Date: 2025-09-11

CREATE TABLE IF NOT EXISTS public.publisher_audit (
  publish_event_id uuid PRIMARY KEY,
  approval_event_ts timestamptz NULL,
  correlation_id uuid NULL,
  artifact_uri text NULL,
  artifact_path text NULL,
  namespace text NULL,
  reviewer text NULL,
  reviewed_at timestamptz NULL,
  status text NOT NULL CHECK (status IN ('published', 'failed')),
  failure_reason text NULL,
  published_event_id uuid NULL,
  public_url text NULL,
  published_at timestamptz NULL,
  processed_at timestamptz NOT NULL DEFAULT timezone('utc', now()),
  meta jsonb NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT timezone('utc', now()),
  updated_at timestamptz NOT NULL DEFAULT timezone('utc', now())
);

CREATE INDEX IF NOT EXISTS idx_publisher_audit_status ON public.publisher_audit (status);
CREATE INDEX IF NOT EXISTS idx_publisher_audit_artifact_path ON public.publisher_audit (artifact_path);
CREATE INDEX IF NOT EXISTS idx_publisher_audit_namespace ON public.publisher_audit (namespace);
CREATE INDEX IF NOT EXISTS idx_publisher_audit_reviewer ON public.publisher_audit (reviewer);
CREATE INDEX IF NOT EXISTS idx_publisher_audit_processed_at ON public.publisher_audit (processed_at DESC);

COMMENT ON TABLE public.publisher_audit IS 'Per-event audit records for the publisher pipeline.';
COMMENT ON COLUMN public.publisher_audit.publish_event_id IS 'Inbound approval event identifier (content.publish.approved.v1).';
COMMENT ON COLUMN public.publisher_audit.artifact_uri IS 'Original S3/MinIO URI supplied by the approval payload.';
COMMENT ON COLUMN public.publisher_audit.artifact_path IS 'Filesystem target chosen by the publisher for the downloaded artifact.';
COMMENT ON COLUMN public.publisher_audit.reviewer IS 'Reviewer identity captured from the approval payload metadata.';
COMMENT ON COLUMN public.publisher_audit.status IS 'Processing status flag (published | failed).';
COMMENT ON COLUMN public.publisher_audit.failure_reason IS 'Exception or validation detail recorded for failed rows.';
COMMENT ON COLUMN public.publisher_audit.meta IS 'JSON metadata blob with slug, namespace, and stage breadcrumbs.';

-- Helper trigger to keep updated_at fresh on updates
CREATE OR REPLACE FUNCTION public.set_current_timestamp_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = timezone('utc', now());
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS set_publisher_audit_updated_at ON public.publisher_audit;
CREATE TRIGGER set_publisher_audit_updated_at
BEFORE UPDATE ON public.publisher_audit
FOR EACH ROW
EXECUTE FUNCTION public.set_current_timestamp_updated_at();
