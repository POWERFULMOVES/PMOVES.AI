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
Firefly PATs are minted per-user via the Firefly UI (host `:8075` → Profile → OAuth →
Personal Access Tokens). Land the baseline via the secrets pipeline (`FIREFLY_PAT`), or have
the mounting harness inject a per-tenant PAT per request. Then a real `list_accounts` returns
that tenant's ledger.

Mounts into A0 (`A0_SET_mcp_servers`) and dsh (`pmoves/config/dsh/pmoves.cordis.patch.yml`)
the same way as cipher/notebook — streamable-http `…/mcp` + Bearer.
