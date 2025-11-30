-- Media analysis tables for detections, segments, emotions
-- Date: 2025-09-10

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

ALTER TABLE public.detections ADD COLUMN IF NOT EXISTS namespace text;
ALTER TABLE public.detections ALTER COLUMN namespace SET DEFAULT 'pmoves';
UPDATE public.detections SET namespace = 'pmoves' WHERE namespace IS NULL OR namespace = '';

DROP INDEX IF EXISTS idx_detections_video_ts;
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

ALTER TABLE public.segments ADD COLUMN IF NOT EXISTS namespace text;
ALTER TABLE public.segments ALTER COLUMN namespace SET DEFAULT 'pmoves';
UPDATE public.segments SET namespace = 'pmoves' WHERE namespace IS NULL OR namespace = '';

DROP INDEX IF EXISTS idx_segments_video_start;
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

ALTER TABLE public.emotions ADD COLUMN IF NOT EXISTS namespace text;
ALTER TABLE public.emotions ALTER COLUMN namespace SET DEFAULT 'pmoves';
UPDATE public.emotions SET namespace = 'pmoves' WHERE namespace IS NULL OR namespace = '';

DROP INDEX IF EXISTS idx_emotions_video_ts;
CREATE INDEX IF NOT EXISTS idx_emotions_namespace_video_ts
  ON public.emotions (namespace, video_id, ts_seconds);
CREATE INDEX IF NOT EXISTS idx_emotions_label
  ON public.emotions (label);
