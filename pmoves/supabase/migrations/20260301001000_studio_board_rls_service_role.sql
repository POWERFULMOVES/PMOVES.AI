-- Ensure render-webhook/service-role writes to public.studio_board work when
-- anonymous access is disabled.

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'service_role') THEN
    ALTER ROLE service_role BYPASSRLS;
  END IF;
END $$;

GRANT USAGE ON SCHEMA public TO anon, authenticated, service_role;

DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name = 'studio_board'
  ) THEN
    EXECUTE 'GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.studio_board TO anon, authenticated, service_role';
    EXECUTE 'ALTER TABLE public.studio_board ENABLE ROW LEVEL SECURITY';
  END IF;

  IF EXISTS (
    SELECT 1 FROM information_schema.sequences
    WHERE sequence_schema = 'public' AND sequence_name = 'studio_board_id_seq'
  ) THEN
    EXECUTE 'GRANT USAGE, SELECT ON SEQUENCE public.studio_board_id_seq TO anon, authenticated, service_role';
  END IF;
END $$;

DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name = 'studio_board'
  ) AND NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname = 'public'
      AND tablename = 'studio_board'
      AND policyname = 'studio_board_anon_all'
  ) THEN
    CREATE POLICY studio_board_anon_all
      ON public.studio_board
      FOR ALL
      TO anon
      USING (true)
      WITH CHECK (true);
  END IF;

  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name = 'studio_board'
  ) AND NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname = 'public'
      AND tablename = 'studio_board'
      AND policyname = 'studio_board_authenticated_all'
  ) THEN
    CREATE POLICY studio_board_authenticated_all
      ON public.studio_board
      FOR ALL
      TO authenticated
      USING (true)
      WITH CHECK (true);
  END IF;

  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name = 'studio_board'
  ) AND NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname = 'public'
      AND tablename = 'studio_board'
      AND policyname = 'studio_board_service_role_all'
  ) THEN
    CREATE POLICY studio_board_service_role_all
      ON public.studio_board
      FOR ALL
      TO service_role
      USING (true)
      WITH CHECK (true);
  END IF;
END $$;
