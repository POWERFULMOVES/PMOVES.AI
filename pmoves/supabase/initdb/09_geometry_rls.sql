-- Enable RLS and add permissive read policies for Geometry Bus tables (authenticated only)
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

-- Tenant-scoped read policies for Geometry Bus tables
-- SECURITY: Uses namespace-based tenant isolation via app.current_tenant setting
-- NOTE: Set 'app.current_tenant' with SET LOCAL app.current_tenant = 'tenant_name';
-- HARDENED: Removed 'pmoves' fallback - requires explicit tenant for all access
-- HARDENED: Requires authentication (TO authenticated) for JWT-based access
DO $$
DECLARE
  -- Newer geometry tables store tenant in meta->>'namespace' rather than a
  -- dedicated namespace column. Resolve expression per table at runtime.
  -- This keeps bootstrap compatible across schema revisions.
  anchors_ns_expr text := CASE
    WHEN EXISTS (
      SELECT 1 FROM information_schema.columns
      WHERE table_schema='public' AND table_name='anchors' AND column_name='namespace'
    ) THEN 'namespace'
    ELSE '(meta->>''namespace'')'
  END;
  constellations_ns_expr text := CASE
    WHEN EXISTS (
      SELECT 1 FROM information_schema.columns
      WHERE table_schema='public' AND table_name='constellations' AND column_name='namespace'
    ) THEN 'namespace'
    ELSE '(meta->>''namespace'')'
  END;
  shape_points_ns_expr text := CASE
    WHEN EXISTS (
      SELECT 1 FROM information_schema.columns
      WHERE table_schema='public' AND table_name='shape_points' AND column_name='namespace'
    ) THEN 'namespace'
    ELSE '(meta->>''namespace'')'
  END;
  shape_index_ns_expr text := CASE
    WHEN EXISTS (
      SELECT 1 FROM information_schema.columns
      WHERE table_schema='public' AND table_name='shape_index' AND column_name='namespace'
    ) THEN 'namespace'
    ELSE '(meta->>''namespace'')'
  END;
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='public' AND tablename='anchors' AND policyname='read_anchors_tenant'
  ) THEN
    EXECUTE format(
      'CREATE POLICY read_anchors_tenant ON public.anchors FOR SELECT TO authenticated USING (%s = current_setting(''app.current_tenant'', true))',
      anchors_ns_expr
    );
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='public' AND tablename='constellations' AND policyname='read_constellations_tenant'
  ) THEN
    EXECUTE format(
      'CREATE POLICY read_constellations_tenant ON public.constellations FOR SELECT TO authenticated USING (%s = current_setting(''app.current_tenant'', true))',
      constellations_ns_expr
    );
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='public' AND tablename='shape_points' AND policyname='read_shape_points_tenant'
  ) THEN
    EXECUTE format(
      'CREATE POLICY read_shape_points_tenant ON public.shape_points FOR SELECT TO authenticated USING (%s = current_setting(''app.current_tenant'', true))',
      shape_points_ns_expr
    );
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='public' AND tablename='shape_index' AND policyname='read_shape_index_tenant'
  ) THEN
    EXECUTE format(
      'CREATE POLICY read_shape_index_tenant ON public.shape_index FOR SELECT TO authenticated USING (%s = current_setting(''app.current_tenant'', true))',
      shape_index_ns_expr
    );
  END IF;
END$$;

-- No write policies: inserts/updates/deletes require service role (bypass RLS)
