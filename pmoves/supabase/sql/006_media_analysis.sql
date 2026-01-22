-- Media analysis tables (dev RLS)
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

DO $$ BEGIN
  CREATE POLICY detections_anon_all ON public.detections FOR ALL TO anon USING (true) WITH CHECK (true);
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN
  CREATE POLICY segments_anon_all ON public.segments FOR ALL TO anon USING (true) WITH CHECK (true);
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN
  CREATE POLICY emotions_anon_all ON public.emotions FOR ALL TO anon USING (true) WITH CHECK (true);
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
