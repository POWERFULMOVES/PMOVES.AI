CREATE TABLE IF NOT EXISTS public.archon_settings (
    key text PRIMARY KEY,
    value text,
    encrypted_value text,
    is_encrypted boolean DEFAULT false,
    category text,
    description text,
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now()
);

COMMENT ON TABLE public.archon_settings IS 'Configuration and credentials store for the Archon agent runtime.';

GRANT SELECT ON TABLE public.archon_settings TO anon;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.archon_settings TO authenticated;
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'pmoves') THEN
        EXECUTE 'GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.archon_settings TO pmoves';
    END IF;
END;
$$;
