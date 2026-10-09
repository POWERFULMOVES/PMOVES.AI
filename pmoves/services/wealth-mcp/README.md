# wealth-mcp

MCP wrapper for **Firefly III** (self-hosted personal finance). Build once, mount by any
agent — the next app-as-plugin cassette after notebook-mcp + cipher.

## Tools
`mcp__wealth__list_accounts` · `list_transactions` · `search_transactions` · `create_transaction`
— thin wrappers over Firefly's `/api/v1` (JSON:API). `create_transaction` writes to the ledger;
the caller's PAT scopes what it can do.

## Tenancy — supports BOTH Firefly models
The wrapper is tenancy-agnostic; the tenant seam lives in the mounting harness:
- **B (shared Firefly + per-tenant PATs):** the harness sets a per-request
  `Authorization: Bearer <that tenant's Firefly PAT>` — this server forwards it verbatim.
- **A (per-tenant Firefly instances):** point `WEALTH_MCP_FIREFLY_URL` at that tenant's
  instance per workspace.
Baseline `FIREFLY_PAT` env is the fallback when no inbound header is set.

## Env
- `FIREFLY_API_URL` — default `http://firefly:8080/api/v1` (in-network alias `firefly`).
- `FIREFLY_PAT` — baseline Personal Access Token (per-request Bearer wins).
- `MCP_HOST`/`MCP_PORT`/`MCP_TRANSPORT` — streamable-http on :8092 (host-published :8208).

## Deploy
`make -C pmoves rebuild-svc SVC=wealth-mcp`. Reproducible build via uv + committed
`requirements.lock` (uv-cassettes skill). Verified: container healthy, reaches Firefly
(`/api/v1/accounts` → 401 without a PAT = live + auth-gated).

## Provision the PAT (operator)
**Automated (baseline):** `make -C pmoves firefly-automint`. Firefly runs under
`remote_user_guard`, so web `/register` is disabled and there is no `user:create` artisan;
the automint provisions the user via the trusted `Remote-User` header, mints a passport PAT
in-container, and lands it as `FIREFLY_ACCESS_TOKEN` through the canonical secrets flow
(`secrets-rotate` → env.shared + CGP bundle + tier env files). Then recreate this service.
Re-running it supersedes the previous baseline PAT: once the landed token round-trips, older
tokens of the same name are revoked in Firefly, and a run that fails after minting revokes the
token it just created and scrubs the in-container temp files. It refuses to run on a node that
carries a CI-pulled CHIT bundle (`secrets-rotate` would replace it and drop prod-only keys);
re-pull first or set `FIREFLY_AUTOMINT_ALLOW_BUNDLE_REPLACE=1` knowingly.

**Manual / per-tenant:** mint per-user in the Firefly UI (host `:8075` → Profile → OAuth →
Personal Access Tokens), or have the mounting harness inject a per-tenant PAT per request.
Then a real `list_accounts` returns that tenant's ledger.

Mounts into A0 (`A0_SET_mcp_servers`) and dsh (`pmoves/config/dsh/pmoves.cordis.patch.yml`)
the same way as cipher/notebook — streamable-http `…/mcp` + Bearer.
