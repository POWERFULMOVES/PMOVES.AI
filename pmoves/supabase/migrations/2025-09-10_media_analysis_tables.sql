-- Media analysis tables for detections, segments, emotions
-- Date: 2025-09-10

CREATE TABLE IF NOT EXISTS public.detections (
  id            bigserial PRIMARY KEY,
  video_id      text,
  ts_seconds    double precision,
  label         text,
  score         double precision,
  frame_uri     text,
  meta          jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_detections_video_ts
  ON public.detections (video_id, ts_seconds);
CREATE INDEX IF NOT EXISTS idx_detections_label
  ON public.detections (label);

CREATE TABLE IF NOT EXISTS public.segments (
  id            bigserial PRIMARY KEY,
  video_id      text,
  label         text,
  score         double precision,
  ts_start      double precision,
  ts_end        double precision,
  uri           text,
  meta          jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_segments_video_start
  ON public.segments (video_id, ts_start);
CREATE INDEX IF NOT EXISTS idx_segments_label
  ON public.segments (label);

CREATE TABLE IF NOT EXISTS public.emotions (
  id            bigserial PRIMARY KEY,
  video_id      text,
  ts_seconds    double precision,
  label         text,
  score         double precision,
  speaker       text,
  frame_uri     text,
  meta          jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_emotions_video_ts
  ON public.emotions (video_id, ts_seconds);
CREATE INDEX IF NOT EXISTS idx_emotions_label
  ON public.emotions (label);
