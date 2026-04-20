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

-- Hardened RLS: deny anon access to credentials store (H-04)
GRANT SELECT ON TABLE public.archon_settings TO authenticated;
GRANT ALL ON TABLE public.archon_settings TO service_role;
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'pmoves') THEN
        EXECUTE 'GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.archon_settings TO pmoves';
    END IF;
END;
$$;

ALTER TABLE public.archon_settings ENABLE ROW LEVEL SECURITY;

-- Deny anon entirely
DO $$ BEGIN
  CREATE POLICY archon_settings_anon_deny ON public.archon_settings
    FOR ALL TO anon USING (false) WITH CHECK (false);
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- Authenticated: read-only
DO $$ BEGIN
  CREATE POLICY archon_settings_auth_read ON public.archon_settings
    FOR SELECT TO authenticated USING (true);
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- Service role: full access
DO $$ BEGIN
  CREATE POLICY archon_settings_svc ON public.archon_settings
    FOR ALL TO service_role USING (true) WITH CHECK (true);
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;
