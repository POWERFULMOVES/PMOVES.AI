CREATE TABLE IF NOT EXISTS public.detections (
  id            bigserial PRIMARY KEY,
  namespace     text DEFAULT 'pmoves',
  video_id      text,
  ts_seconds    double precision,
  label         text,
  score         double precision,
  frame_uri     text,
  meta          jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_detections_namespace_video_ts
  ON public.detections (namespace, video_id, ts_seconds);
CREATE INDEX IF NOT EXISTS idx_detections_label
  ON public.detections (label);

CREATE TABLE IF NOT EXISTS public.segments (
  id            bigserial PRIMARY KEY,
  namespace     text DEFAULT 'pmoves',
  video_id      text,
  label         text,
  score         double precision,
  ts_start      double precision,
  ts_end        double precision,
  uri           text,
  meta          jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_segments_namespace_video_start
  ON public.segments (namespace, video_id, ts_start);
CREATE INDEX IF NOT EXISTS idx_segments_label
  ON public.segments (label);

CREATE TABLE IF NOT EXISTS public.emotions (
  id            bigserial PRIMARY KEY,
  namespace     text DEFAULT 'pmoves',
  video_id      text,
  ts_seconds    double precision,
  label         text,
  score         double precision,
  speaker       text,
  frame_uri     text,
  meta          jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_emotions_namespace_video_ts
  ON public.emotions (namespace, video_id, ts_seconds);
CREATE INDEX IF NOT EXISTS idx_emotions_label
  ON public.emotions (label);

GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.detections TO anon;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.segments TO anon;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.emotions TO anon;

ALTER TABLE public.detections ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.segments ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.emotions ENABLE ROW LEVEL SECURITY;

-- SECURITY: Tenant-scoped RLS policies with namespace isolation
-- Uses app.current_tenant setting to isolate data by namespace column
-- Set tenant with: SET LOCAL app.current_tenant = 'tenant_name';
DO $$ BEGIN
  CREATE POLICY detections_tenant_isolation ON public.detections FOR ALL TO anon
  USING (namespace = current_setting('app.current_tenant', true) OR namespace = 'pmoves')
  WITH CHECK (namespace = current_setting('app.current_tenant', true) OR namespace = 'pmoves');
EXCEPTION WHEN duplicate_object THEN
  -- Drop old insecure policy if exists
  DROP POLICY IF EXISTS detections_anon_all ON public.detections;
  CREATE POLICY detections_tenant_isolation ON public.detections FOR ALL TO anon
  USING (namespace = current_setting('app.current_tenant', true) OR namespace = 'pmoves')
  WITH CHECK (namespace = current_setting('app.current_tenant', true) OR namespace = 'pmoves');
END $$;

DO $$ BEGIN
  CREATE POLICY segments_tenant_isolation ON public.segments FOR ALL TO anon
  USING (namespace = current_setting('app.current_tenant', true) OR namespace = 'pmoves')
  WITH CHECK (namespace = current_setting('app.current_tenant', true) OR namespace = 'pmoves');
EXCEPTION WHEN duplicate_object THEN
  DROP POLICY IF EXISTS segments_anon_all ON public.segments;
  CREATE POLICY segments_tenant_isolation ON public.segments FOR ALL TO anon
  USING (namespace = current_setting('app.current_tenant', true) OR namespace = 'pmoves')
  WITH CHECK (namespace = current_setting('app.current_tenant', true) OR namespace = 'pmoves');
END $$;

DO $$ BEGIN
  CREATE POLICY emotions_tenant_isolation ON public.emotions FOR ALL TO anon
  USING (namespace = current_setting('app.current_tenant', true) OR namespace = 'pmoves')
  WITH CHECK (namespace = current_setting('app.current_tenant', true) OR namespace = 'pmoves');
EXCEPTION WHEN duplicate_object THEN
  DROP POLICY IF EXISTS emotions_anon_all ON public.emotions;
  CREATE POLICY emotions_tenant_isolation ON public.emotions FOR ALL TO anon
  USING (namespace = current_setting('app.current_tenant', true) OR namespace = 'pmoves')
  WITH CHECK (namespace = current_setting('app.current_tenant', true) OR namespace = 'pmoves');
END $$;
