# notebook-mcp

The **"build once, mount twice"** wrapper for PMOVES Open Notebook — an MCP server
exposing Open Notebook's REST API as MCP tools so **any agent** can use notebook,
not just Agent Zero.

## Why

Open Notebook was reachable only through the `pmoves_notes` **Agent Zero plugin**
(native Python tools). This server exposes the *same* operations over the MCP
protocol, so every MCP-consuming agent mounts one wrapper:

- **Agent Zero** — point its runtime MCP client (`:8081`) at this server, OR keep the
  native `pmoves_notes` plugin (both call the same Open Notebook API).
- **deepseek-harness** — one `cordis.yml` row via `@deepseek-ai/dsh-mcp-client`
  (`transport: streamable-http`, `url: http://notebook-mcp:8092/mcp`). Tools surface
  as `mcp__notebook__save_note` / `mcp__notebook__search_notes`.
- Any other MCP client (Claude Code, Codex, …).

## Tools

| tool | Open Notebook call | args |
|---|---|---|
| `save_note` | `POST /api/notes` (tags folded into body) | `content` (req), `title`, `tags[]` |
| `search_notes` | `POST /api/search` (notes, text) | `query` (req), `limit` (1-50) |

Both mirror the proven `pmoves_notes` plugin calls and publish best-effort NATS
events (`agent.notes.saved.v1` / `agent.notes.searched.v1`).

## Config (env)

| var | default | note |
|---|---|---|
| `OPEN_NOTEBOOK_API_URL` | `http://open-notebook:5055` | internal alias |
| `OPEN_NOTEBOOK_API_TOKEN` | _(empty)_ | shared **fallback** Bearer; warns on plain-http |
| `NOTEBOOK_MCP_TENANT_TOKEN_HEADER` | `X-Open-Notebook-Token` | inbound header carrying the caller's token |
| `NOTEBOOK_MCP_REQUIRE_TENANT_TOKEN` | `false` | `true` = fail closed, no shared fallback |
| `MCP_HOST` / `MCP_PORT` | `0.0.0.0` / `8092` | streamable-http bind |
| `MCP_TRANSPORT` | `streamable-http` | `sse` \| `stdio` also supported |
| `NATS_URL` | `nats://nats:pmoves@nats:4222` | best-effort events |

## Multi-tenancy

The Open Notebook credential is resolved **per request**, not per process:

1. the token on the in-flight MCP request (`NOTEBOOK_MCP_TENANT_TOKEN_HEADER`,
   default `X-Open-Notebook-Token`) — this is the seam a mounting harness fills
   (dsh `ctx.credentials`, an A0 per-context header, a gateway), so tenant A's
   call reaches tenant A's notebook and nobody else's;
2. otherwise `OPEN_NOTEBOOK_API_TOKEN`, a **single-tenant convenience fallback**.

Step 2 is the whole risk surface: if two tenants can reach one instance and
neither sends a header, both silently share one Open Notebook account —
`search_notes` discloses across tenants and `save_note` writes across them.

**If more than one tenant can reach this server, set
`NOTEBOOK_MCP_REQUIRE_TENANT_TOKEN=true`.** The shared fallback is then disabled
outright: a request with no credential is refused with an explanatory tool error
instead of borrowing the shared account. The startup line prints which mode is
in effect.

The compose stanza ships the fallback **enabled** (no `REQUIRE_TENANT_TOKEN`)
and binds `127.0.0.1` — i.e. single-tenant by default. Flip the flag in the same
change that exposes this service to a second tenant.

> Open Notebook `surreal_data` dual-writer hazard: this server and the standalone
> Open Notebook UI both write one SurrealDB. Prefer a single writer per data path.
