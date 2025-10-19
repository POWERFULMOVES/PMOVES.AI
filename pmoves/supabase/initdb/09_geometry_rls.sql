-- Enable RLS and add permissive read policies for Geometry Bus tables
-- Date: 2025-09-08

-- Optional read-only role for direct DB access (non-Supabase JWT)
DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'pmoves_ui') THEN
    CREATE ROLE pmoves_ui NOLOGIN;
  END IF;
END$$;

GRANT USAGE ON SCHEMA public TO pmoves_ui;
GRANT SELECT ON public.anchors, public.constellations, public.shape_points, public.shape_index TO pmoves_ui;

-- Enable RLS
ALTER TABLE public.anchors ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.constellations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.shape_points ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.shape_index ENABLE ROW LEVEL SECURITY;

-- Permissive read policies (dev). Tighten for prod (e.g., tenant/namespace scoping).
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='public' AND tablename='anchors' AND policyname='read_anchors_all'
  ) THEN
    EXECUTE 'CREATE POLICY read_anchors_all ON public.anchors FOR SELECT USING (true)';
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='public' AND tablename='constellations' AND policyname='read_constellations_all'
  ) THEN
    EXECUTE 'CREATE POLICY read_constellations_all ON public.constellations FOR SELECT USING (true)';
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='public' AND tablename='shape_points' AND policyname='read_shape_points_all'
  ) THEN
    EXECUTE 'CREATE POLICY read_shape_points_all ON public.shape_points FOR SELECT USING (true)';
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='public' AND tablename='shape_index' AND policyname='read_shape_index_all'
  ) THEN
    EXECUTE 'CREATE POLICY read_shape_index_all ON public.shape_index FOR SELECT USING (true)';
  END IF;
END$$;

-- No write policies: inserts/updates/deletes require service role (bypass RLS)
