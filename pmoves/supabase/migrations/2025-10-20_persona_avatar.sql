-- Persona avatar + geometry linkage
-- Date: 2025-10-20

CREATE TABLE IF NOT EXISTS public.persona_avatar (
  id                       bigserial PRIMARY KEY,
  persona_slug             text NOT NULL,
  persona_name             text NULL,
  namespace                text NOT NULL DEFAULT 'pmoves.art',
  avatar_uri               text NOT NULL,
  thumbnail_uri            text NULL,
  geometry_constellation_id uuid NULL REFERENCES public.constellations(id) ON DELETE SET NULL,
  geometry_namespace       text NULL,
  meta                     jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at               timestamptz NOT NULL DEFAULT timezone('utc', now()),
  updated_at               timestamptz NOT NULL DEFAULT timezone('utc', now())
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_persona_avatar_namespace_slug
  ON public.persona_avatar (namespace, persona_slug);

CREATE INDEX IF NOT EXISTS idx_persona_avatar_geom_constellation
  ON public.persona_avatar (geometry_constellation_id);

ALTER TABLE public.persona_avatar ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
  DROP POLICY IF EXISTS read_persona_avatar_all ON public.persona_avatar;
  CREATE POLICY read_persona_avatar_all ON public.persona_avatar FOR SELECT USING (true);
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- Reuse the shared updated_at trigger helper
DROP TRIGGER IF EXISTS set_persona_avatar_updated_at ON public.persona_avatar;
CREATE TRIGGER set_persona_avatar_updated_at
BEFORE UPDATE ON public.persona_avatar
FOR EACH ROW
EXECUTE FUNCTION public.set_current_timestamp_updated_at();
