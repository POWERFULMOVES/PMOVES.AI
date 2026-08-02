-- Cipher per-agent token registry and access log (Phase B PR 2)
-- See pmoves/docs/TAC/TAC_CIPHER_VILLAGE.md

-- Token registry: one row per minted token, bound to an agent_id and scopes.
CREATE TABLE IF NOT EXISTS pmoves_core.cipher_agent_tokens (
    token_uuid UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id TEXT NOT NULL,
    scopes TEXT[] NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    revoked_at TIMESTAMPTZ NULL,
    created_by TEXT NULL
);

-- Fast lookup for active token resolution: WHERE token_uuid = $1 AND revoked_at IS NULL
CREATE INDEX IF NOT EXISTS idx_cipher_agent_tokens_lookup
    ON pmoves_core.cipher_agent_tokens(token_uuid, revoked_at)
    WHERE revoked_at IS NULL;

-- Agent index for audit and revocation
CREATE INDEX IF NOT EXISTS idx_cipher_agent_tokens_agent
    ON pmoves_core.cipher_agent_tokens(agent_id, revoked_at);

-- Access log: one row per authenticated tool use
CREATE TABLE IF NOT EXISTS pmoves_core.cipher_access_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id TEXT NOT NULL,
    tool TEXT NOT NULL,
    memory_id TEXT NULL,
    ts TIMESTAMPTZ NOT NULL DEFAULT now(),
    harness TEXT NULL,
    model TEXT NULL
);

CREATE INDEX IF NOT EXISTS idx_cipher_access_log_agent_ts
    ON pmoves_core.cipher_access_log(agent_id, ts DESC);

CREATE INDEX IF NOT EXISTS idx_cipher_access_log_tool_ts
    ON pmoves_core.cipher_access_log(tool, ts DESC);

COMMENT ON TABLE pmoves_core.cipher_agent_tokens IS 'Per-agent Bearer tokens for cipher authentication (Phase B PR 2)';
COMMENT ON TABLE pmoves_core.cipher_access_log IS 'Audit trail of authenticated cipher tool usage';

-- Enable RLS + grant service_role access (Codex P1: without this, PostgREST
-- cannot insert or query the token table even with Content-Profile: pmoves_core)
ALTER TABLE pmoves_core.cipher_agent_tokens ENABLE ROW LEVEL SECURITY;
ALTER TABLE pmoves_core.cipher_access_log ENABLE ROW LEVEL SECURITY;

GRANT SELECT, INSERT, UPDATE, DELETE ON pmoves_core.cipher_agent_tokens TO service_role;
GRANT SELECT, INSERT ON pmoves_core.cipher_access_log TO service_role;

-- Service role bypasses RLS by default in Supabase (auth.role() = 'service_role')
-- No explicit POLICY needed — service_role has full access.
