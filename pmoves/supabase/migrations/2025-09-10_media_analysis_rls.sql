-- Media analysis RLS policies (dev-friendly defaults)
-- Date: 2025-09-10

GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.detections TO anon;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.segments TO anon;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.emotions TO anon;

ALTER TABLE public.detections ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.segments ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.emotions ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
  CREATE POLICY detections_anon_all
    ON public.detections
    FOR ALL
    TO anon
    USING (true)
    WITH CHECK (true);
EXCEPTION
  WHEN duplicate_object THEN NULL;
END;
$$;

DO $$
BEGIN
  CREATE POLICY segments_anon_all
    ON public.segments
    FOR ALL
    TO anon
    USING (true)
    WITH CHECK (true);
EXCEPTION
  WHEN duplicate_object THEN NULL;
END;
$$;

DO $$
BEGIN
  CREATE POLICY emotions_anon_all
    ON public.emotions
    FOR ALL
    TO anon
    USING (true)
    WITH CHECK (true);
EXCEPTION
  WHEN duplicate_object THEN NULL;
END;
$$;
