-- Enable RLS and add authentication-required policies for Geometry Bus tables
-- Date: 2025-09-08
-- Updated: 2026-01-07 - Require authentication for all access

-- Optional read-only role for direct DB access (non-Supabase JWT)
DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'pmoves_ui') THEN
    CREATE ROLE pmoves_ui;
  END IF;
END$$;

GRANT USAGE ON SCHEMA public TO pmoves_ui;
GRANT SELECT ON public.anchors, public.constellations, public.shape_points, public.shape_index TO pmoves_ui;

-- Enable RLS
ALTER TABLE public.anchors ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.constellations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.shape_points ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.shape_index ENABLE ROW LEVEL SECURITY;

-- Authentication-required read policies
-- All reads require a valid JWT (auth.uid() IS NOT NULL)
-- For production, consider adding tenant/namespace scoping
DROP POLICY IF EXISTS read_anchors_all ON public.anchors;
CREATE POLICY read_anchors_all ON public.anchors
FOR SELECT USING (auth.uid() IS NOT NULL);

DROP POLICY IF EXISTS read_constellations_all ON public.constellations;
CREATE POLICY read_constellations_all ON public.constellations
FOR SELECT USING (auth.uid() IS NOT NULL);

DROP POLICY IF EXISTS read_shape_points_all ON public.shape_points;
CREATE POLICY read_shape_points_all ON public.shape_points
FOR SELECT USING (auth.uid() IS NOT NULL);

DROP POLICY IF EXISTS read_shape_index_all ON public.shape_index;
CREATE POLICY read_shape_index_all ON public.shape_index
FOR SELECT USING (auth.uid() IS NOT NULL);

-- No write policies: inserts/updates/deletes require service role (bypass RLS)
