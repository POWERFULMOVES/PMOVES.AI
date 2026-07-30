# cipher-village-pr-2-per-agent-tokens

Field brief for **any implementation agent** (KiloCode / claude / kimi / crush) —
implement Phase B PR 2 of the Cipher Village architecture. PR 1 (agentId
parameter) already shipped on `feat/cipher-agent-scope`; this PR adds the
auth enforcement layer.

Source architecture: `pmoves/docs/TAC/TAC_CIPHER_VILLAGE.md` (§Phase B PR 2).
PR 1 reference: `feat/cipher-agent-scope` commit `a878f374`.

## Arguments

- `agent_id` (string, required): the agent identity to mint a token for
  (e.g. `crush-spark`, `claude-4090`, `kimi-spark`). Must match
  `signing_identity_cards.yaml` `agent_id` field.
- `scopes` (string[], optional, default `["memory:read", "memory:write", "reasoning:read", "reasoning:write", "session:read", "session:write"]`):
  permission scopes for the token.
- `ttl_days` (number, optional, default 90): token lifetime in days.

## Implementation

### 1. Supabase schema migration

Create `pmoves/supabase/migrations/<timestamp>_cipher_agent_tokens.sql`:

```sql
-- Cipher per-agent token registry
CREATE TABLE IF NOT EXISTS pmoves_core.cipher_agent_tokens (
  token_uuid UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  agent_id TEXT NOT NULL,
  scopes TEXT[] NOT NULL DEFAULT '{"memory:read","memory:write","reasoning:read","reasoning:write","session:read","session:write"}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  revoked_at TIMESTAMPTZ,
  created_by TEXT NOT NULL DEFAULT 'bootstrap',
  CONSTRAINT valid_agent_id CHECK (agent_id ~ '^[a-z0-9][a-z0-9-]*$')
);

CREATE INDEX idx_cipher_agent_tokens_agent_id ON pmoves_core.cipher_agent_tokens(agent_id) WHERE revoked_at IS NULL;

-- The token secret is returned ONLY at mint time (never stored in plaintext).
-- The token_uuid is the lookup key; the secret is `hex(token_uuid)` prefixed with `cipher_`.
-- This avoids needing a separate secret store — the UUID IS the token.
-- Revocation = SET revoked_at = now().

COMMENT ON TABLE pmoves_core.cipher_agent_tokens IS
  'Per-agent cipher auth tokens. The token string is `cipher_<token_uuid_hex>`. Revocation via revoked_at timestamp. Managed by make target cipher-mint-token.';

-- Enable RLS
ALTER TABLE pmoves_core.cipher_agent_tokens ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Service role full access" ON pmoves_core.cipher_agent_tokens
  FOR ALL USING (auth.role() = 'service_role');
```

### 2. Extend auth.ts middleware

Modify `Pmoves-cipher/src/pmoves/auth.ts`:

- Add `tokenToAgent(token: string): {agentId: string, scopes: string[]} | null`
  — strips `cipher_` prefix, queries Supabase `pmoves_core.cipher_agent_tokens`
  by `token_uuid`, returns `{agentId, scopes}` if active (not revoked), else null.
- Modify `createPmovesAuthMiddleware` to:
  - On valid token: attach `req.agentId = agentId` and `req.scopes = scopes`
  - On invalid/revoked token: 401
  - On no token + `skipIfUnset=true`: `req.agentId = undefined` (advisory mode)
  - On no token + `skipIfUnset=false`: 401
- Add scope-checking helper: `requireScope(scope: string)` returns middleware
  that checks `req.scopes` includes the scope, else 403.

### 3. Thread req.agentId into MCP tools

Modify `Pmoves-cipher/src/pmoves/mcp-sse.ts`:

- When `req.agentId` is set (enforced mode), override `args.agentId` with it
  (prevents token spoofing — an agent can't claim to be another agent).
- When `req.agentId` is undefined (advisory/dev mode), use `args.agentId` as-is
  (PR 1 behavior).
- Mismatch (token agentId ≠ args.agentId, and args.agentId ≠ "*") → throw 403.

### 4. Make target for token minting

Add to `pmoves/Makefile`:

```makefile
cipher-mint-token: ## Mint a per-agent cipher token. Usage: make cipher-mint-token AGENT=crush-spark
	@test -n "$(AGENT)" || (echo "AGENT is required (e.g. crush-spark)" && exit 1)
	@bash scripts/with-env.sh python3 -c "\
	import os, requests, secrets; \
	url = os.environ.get('SUPABASE_REST_URL', 'http://localhost:8000/rest/v1'); \
	key = os.environ.get('SUPABASE_SERVICE_KEY', ''); \
	r = requests.post(f'{url}/cipher_agent_tokens', json={'agent_id': '$(AGENT)'}, headers={'apikey': key, 'Authorization': f'Bearer {key}'}); \
	r.raise_for_status(); \
	tok = r.json()[0]; print(f'CIPHER_API_TOKEN=cipher_{tok[\"token_uuid\"].replace(\"-\",\"\")}'); \
	print(f'Agent: $(AGENT)  Scopes: {tok[\"scopes\"]}  Expires: never (revoke via SQL)')"
```

### 5. env.shared.example documentation

Add `CIPHER_API_TOKEN` to `pmoves/env.shared.example` tier-agent section with
a comment explaining: "Per-agent cipher auth token. Mint via
`make -C pmoves cipher-mint-token AGENT=<id>`. When unset, cipher runs in
dev-skip mode (advisory agentId, no enforcement)."

## Related

- `pmoves/docs/TAC/TAC_CIPHER_VILLAGE.md` §Phase B PR 2 — canonical spec
- `Pmoves-cipher/src/pmoves/auth.ts` — existing single-token middleware (extend)
- `Pmoves-cipher/src/pmoves/mcp-sse.ts` — PR 1 agentId parameter (enforce here)
- `pmoves/config/signing_identity_cards.yaml` — agent_id source of truth
- `pmoves/supabase/migrations/20260628000000_voice_catalog.sql` — migration format reference

## Notes

- The token IS the UUID (no separate secret store needed). `cipher_<hex>` format.
- Revocation is a SQL UPDATE (`SET revoked_at = now()`), not a delete (audit trail).
- The MCP-SSE transport doesn't pass HTTP headers through the MCP protocol —
  the `Authorization` header is consumed at the Express layer BEFORE the MCP
  handshake. This is why the middleware lives in `auth.ts`, not in MCP code.
- Scopes are checked per-tool (e.g. `pmoves_cipher_store` requires `memory:write`).
- Dev-skip mode (no token) preserves all PR 1 behavior — agents self-declare agentId.
- Test: mint a token for `crush-spark`, set `CIPHER_API_TOKEN=cipher_<hex>`,
  verify `req.agentId === "crush-spark"` overrides any args.agentId.

## Verification

```bash
# 1. Apply migration
make -C pmoves supabase-bootstrap

# 2. Mint token
make -C pmoves cipher-mint-token AGENT=crush-spark
# → prints: CIPHER_API_TOKEN=cipher_<hex>

# 3. Set in env, restart cipher-api
# 4. Verify enforcement:
#    POST /api/memory with header Authorization: Bearer cipher_<hex> + body {agentId: "claude-4090"}
#    → should 403 (token is crush-spark, body claims claude-4090)
# 5. Verify advisory:
#    Unset CIPHER_API_TOKEN, restart, POST with agentId in body → 201 (PR 1 behavior)
```
