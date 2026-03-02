-- Ensure render-webhook/service-role writes to public.studio_board with
-- explicit, non-anonymous RLS predicates.

DO $$
BEGIN
  -- Hardened path: do not mutate role-level BYPASSRLS here.
  PERFORM 1;
END $$;

GRANT USAGE ON SCHEMA public TO service_role;

DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name = 'studio_board'
  ) THEN
    EXECUTE 'REVOKE SELECT, INSERT, UPDATE, DELETE ON TABLE public.studio_board FROM anon, authenticated';
  END IF;

  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name = 'studio_board'
  ) THEN
    EXECUTE 'GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.studio_board TO service_role';
    EXECUTE 'ALTER TABLE public.studio_board ENABLE ROW LEVEL SECURITY';
  END IF;

  IF EXISTS (
    SELECT 1 FROM information_schema.sequences
    WHERE sequence_schema = 'public' AND sequence_name = 'studio_board_id_seq'
  ) THEN
    EXECUTE 'REVOKE USAGE, SELECT ON SEQUENCE public.studio_board_id_seq FROM anon, authenticated';
    EXECUTE 'GRANT USAGE, SELECT ON SEQUENCE public.studio_board_id_seq TO service_role';
  END IF;
END $$;

DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name = 'studio_board'
  ) THEN
    DROP POLICY IF EXISTS studio_board_anon_all ON public.studio_board;
    DROP POLICY IF EXISTS studio_board_authenticated_all ON public.studio_board;
    DROP POLICY IF EXISTS studio_board_service_role_all ON public.studio_board;

    CREATE POLICY studio_board_service_role_all
      ON public.studio_board
      FOR ALL
      TO service_role
      USING (auth.role() = 'service_role')
      WITH CHECK (auth.role() = 'service_role');
  END IF;
END $$;
