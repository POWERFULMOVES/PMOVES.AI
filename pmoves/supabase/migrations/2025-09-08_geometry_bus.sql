-- Geometry Bus (CHIT) minimal schema
-- Date: 2025-09-08

-- Extensions (optional; not strictly required for this minimal schema)
-- Uncomment pgcrypto if you want gen_random_uuid(); some Supabase stacks already enable it.
-- CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Note: We intentionally use float4[] for anchors/spectra to avoid baking a fixed pgvector dimension.
-- If you prefer pgvector, add: CREATE EXTENSION IF NOT EXISTS vector; and replace float4[] with vector(<dim>).

CREATE TABLE IF NOT EXISTS public.anchors (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  kind          text NOT NULL CHECK (kind IN ('text','audio','video','image','latent','multi')),
  dim           integer NOT NULL CHECK (dim > 0),
  anchor        float4[] NULL,
  anchor_enc    jsonb NULL,
  meta          jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.constellations (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  anchor_id       uuid NOT NULL REFERENCES public.anchors(id) ON DELETE CASCADE,
  summary         text NULL,
  radial_min      double precision NULL,
  radial_max      double precision NULL,
  spectrum        float4[] NULL,
  meta            jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.shape_points (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  constellation_id uuid NOT NULL REFERENCES public.constellations(id) ON DELETE CASCADE,
  modality         text NOT NULL CHECK (modality IN ('text','audio','video','image','latent')),
  ref_id           text NOT NULL,                  -- e.g., videos.video_id, transcripts row id, doc id
  t_start          double precision NULL,          -- seconds
  t_end            double precision NULL,          -- seconds
  frame_idx        integer NULL,
  token_start      integer NULL,
  token_end        integer NULL,
  proj             double precision NULL,
  conf             double precision NULL,
  meta             jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at       timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.shape_index (
  shape_id   uuid NOT NULL,
  modality   text NOT NULL,
  ref_id     text NOT NULL,
  loc_hash   text NOT NULL,
  meta       jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (shape_id, modality, ref_id, loc_hash)
);

-- Helpful indexes
CREATE INDEX IF NOT EXISTS idx_shape_points_lookup ON public.shape_points (modality, ref_id);
CREATE INDEX IF NOT EXISTS idx_shape_points_time ON public.shape_points (t_start, t_end);
CREATE INDEX IF NOT EXISTS idx_constellations_anchor ON public.constellations (anchor_id);
CREATE INDEX IF NOT EXISTS idx_shape_index_ref ON public.shape_index (modality, ref_id);
CREATE INDEX IF NOT EXISTS idx_anchors_kind ON public.anchors (kind);
CREATE INDEX IF NOT EXISTS idx_json_meta_anchors ON public.anchors USING GIN (meta);
CREATE INDEX IF NOT EXISTS idx_json_meta_constellations ON public.constellations USING GIN (meta);
CREATE INDEX IF NOT EXISTS idx_json_meta_points ON public.shape_points USING GIN (meta);
CREATE INDEX IF NOT EXISTS idx_json_meta_shape_index ON public.shape_index USING GIN (meta);

-- RLS (optional): leave disabled for dev; enable and add policies later
-- ALTER TABLE public.anchors ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE public.constellations ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE public.shape_points ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE public.shape_index ENABLE ROW LEVEL SECURITY;

