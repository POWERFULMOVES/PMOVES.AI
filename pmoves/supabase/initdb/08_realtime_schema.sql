CREATE SCHEMA IF NOT EXISTS realtime;

CREATE TABLE IF NOT EXISTS realtime.tenants (
    id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    name text NOT NULL,
    external_id text UNIQUE NOT NULL,
    jwt_secret text,
    jwt_jwks jsonb,
    postgres_cdc_default boolean DEFAULT true,
    max_concurrent_users integer,
    max_events_per_second integer,
    max_bytes_per_second integer,
    max_channels_per_client integer,
    max_joins_per_second integer,
    suspend boolean DEFAULT false,
    notify_private_alpha boolean DEFAULT false,
    inserted_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now()
);

INSERT INTO realtime.tenants (name, external_id, jwt_secret)
VALUES ('PMOVES Local', 'realtime', 'pmoves_dev_jwt_secret_32_chars!!')
ON CONFLICT (external_id) DO UPDATE SET
    name = EXCLUDED.name,
    jwt_secret = EXCLUDED.jwt_secret,
    updated_at = now();

GRANT USAGE ON SCHEMA realtime TO service_role, authenticated, anon;
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'pmoves') THEN
        EXECUTE 'GRANT USAGE ON SCHEMA realtime TO pmoves';
    END IF;
END;
$$;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA realtime TO service_role;
GRANT SELECT ON ALL TABLES IN SCHEMA realtime TO authenticated, anon;
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'pmoves') THEN
        EXECUTE 'GRANT SELECT ON ALL TABLES IN SCHEMA realtime TO pmoves';
    END IF;
END;
$$;
