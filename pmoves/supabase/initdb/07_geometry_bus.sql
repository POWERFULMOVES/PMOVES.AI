-- CHIT Geometry Bus core schema
-- Shared by initdb and migrations to keep geometry tables first-class.

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
  ref_id           text NOT NULL,
  t_start          double precision NULL,
  t_end            double precision NULL,
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

-- Helpful indexes for lookups and metadata filters.
CREATE INDEX IF NOT EXISTS idx_shape_points_lookup ON public.shape_points (modality, ref_id);
CREATE INDEX IF NOT EXISTS idx_shape_points_time ON public.shape_points (t_start, t_end);
CREATE INDEX IF NOT EXISTS idx_constellations_anchor ON public.constellations (anchor_id);
CREATE INDEX IF NOT EXISTS idx_shape_index_ref ON public.shape_index (modality, ref_id);
CREATE INDEX IF NOT EXISTS idx_anchors_kind ON public.anchors (kind);
CREATE INDEX IF NOT EXISTS idx_json_meta_anchors ON public.anchors USING GIN (meta);
CREATE INDEX IF NOT EXISTS idx_json_meta_constellations ON public.constellations USING GIN (meta);
CREATE INDEX IF NOT EXISTS idx_json_meta_points ON public.shape_points USING GIN (meta);
CREATE INDEX IF NOT EXISTS idx_json_meta_shape_index ON public.shape_index USING GIN (meta);
