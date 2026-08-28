-- Add missing index on publisher_audit.published_at for recency queries
-- Follow-up from PR #1100 CodeRabbit finding
CREATE INDEX IF NOT EXISTS idx_publisher_audit_published_at
  ON public.publisher_audit(published_at DESC);
