-- Phase 9Q.2: YouTube OAuth cookie refresh workflow
-- Stores encrypted refresh tokens and cookie state for automated YT cookie harvesting.
-- Encrypted columns use Fernet (VAULT_ENC_KEY) — plaintext never hits the DB.
--
-- RLS: service_role gets full access, anon gets nothing.
-- Schema: pmoves_core (matches existing service tables).

BEGIN;

CREATE SCHEMA IF NOT EXISTS pmoves_core;

CREATE TABLE IF NOT EXISTS pmoves_core.yt_oauth_cookies (
    id                        BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id                   TEXT NOT NULL DEFAULT 'darkxside',
    encrypted_refresh_token   TEXT,
    encrypted_access_token    TEXT,
    encrypted_cookies         TEXT,
    encrypted_po_token        TEXT,
    access_token_expires_at   TIMESTAMPTZ,
    refresh_triggered_at      TIMESTAMPTZ,
    refresh_completed_at      TIMESTAMPTZ,
    refresh_status            TEXT CHECK (refresh_status IN ('pending', 'success', 'failed', 'revoked')),
    refresh_error_message     TEXT,
    requires_manual_reauth    BOOLEAN NOT NULL DEFAULT FALSE,
    created_at                TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at                TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT yt_oauth_cookies_user_id_unique UNIQUE (user_id)
);

CREATE OR REPLACE FUNCTION pmoves_core.yt_oauth_cookies_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS yt_oauth_cookies_updated_at_trigger
    ON pmoves_core.yt_oauth_cookies;

CREATE TRIGGER yt_oauth_cookies_updated_at_trigger
    BEFORE UPDATE ON pmoves_core.yt_oauth_cookies
    FOR EACH ROW
    EXECUTE FUNCTION pmoves_core.yt_oauth_cookies_updated_at();

ALTER TABLE pmoves_core.yt_oauth_cookies ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS yt_oauth_cookies_service_role_all
    ON pmoves_core.yt_oauth_cookies;

CREATE POLICY yt_oauth_cookies_service_role_all
    ON pmoves_core.yt_oauth_cookies
    FOR ALL
    USING (current_setting('request.jwt.claim.role', true) = 'service_role')
    WITH CHECK (current_setting('request.jwt.claim.role', true) = 'service_role');

CREATE INDEX IF NOT EXISTS idx_yt_oauth_cookies_status
    ON pmoves_core.yt_oauth_cookies (refresh_status, refresh_completed_at);

COMMENT ON TABLE pmoves_core.yt_oauth_cookies IS
    'Phase 9Q.2: Encrypted YouTube OAuth credentials and cookie state for automated harvesting.';

COMMIT;
