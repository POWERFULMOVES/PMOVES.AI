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
| `OPEN_NOTEBOOK_API_TOKEN` | _(empty)_ | Bearer; warns on plain-http |
| `MCP_HOST` / `MCP_PORT` | `0.0.0.0` / `8092` | streamable-http bind |
| `MCP_TRANSPORT` | `streamable-http` | `sse` \| `stdio` also supported |
| `NATS_URL` | `nats://nats:pmoves@nats:4222` | best-effort events |

## Multi-tenancy

This server is a **thin, stateless REST→MCP bridge** reading one Open Notebook
token from env. The per-tenant seam — mapping an agent's workspace/session identity
to that tenant's Notebook credential — lives in the **mounting harness** (dsh
`ctx.credentials`, or an A0 per-context header), not here. Keep it that way so the
same wrapper serves every tenant.

> Open Notebook `surreal_data` dual-writer hazard: this server and the standalone
> Open Notebook UI both write one SurrealDB. Prefer a single writer per data path.
