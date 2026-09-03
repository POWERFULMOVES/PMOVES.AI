# Handoff — notebook-mcp: build-once-mount-twice wrapper for Open Notebook (2026-09-02)

**Node:** 5090 · **Lane:** apps-as-MCP-plugins (operator-approved entry lane, option 2) · **Author:** 5090-CLAUDE

## Why (provable reason for the protected-file edits)

The operator's direction: multi-tenant apps become **plugins usable by any agent**
([[project_apps_as_mcp_plugins_architecture]]). Chosen first lane (option 2): prove the pattern
end-to-end with **notebook**. Open Notebook was reachable only via the `pmoves_notes` Agent Zero
**plugin** (native Python tools). This builds `pmoves/services/notebook-mcp/` — an MCP server that
exposes the *same* proven Open Notebook calls (`POST /api/notes`, `POST /api/search`) over the MCP
protocol, so A0 (runtime MCP client `:8081`), deepseek-harness (`dsh-mcp-client`), and any other
MCP consumer mount ONE wrapper. Tools surface as `mcp__notebook__save_note` / `..._search_notes`.

## Protected-file edits this lane needs

1. **Dockerfile** `pmoves/services/notebook-mcp/Dockerfile` (KNOWN_ROAD=dockerfile) — python:3.12-slim,
   non-root, streamable-http MCP on :8092.
2. **compose** a `notebook-mcp` service (KNOWN_ROAD=compose) on `pmoves_app` (to reach `open-notebook`
   and be reachable by A0/dsh), reading `OPEN_NOTEBOOK_API_URL`/`OPEN_NOTEBOOK_API_TOKEN`.

## Not in this change (follow-ups)

- Wire A0's runtime MCP client (`:8081` / `seed_agent_zero_mcp.py`) at `http://notebook-mcp:8092/mcp`
  — OR keep the native `pmoves_notes` plugin (both hit the same API). A0 side is already production
  via the plugin; the MCP mount is the "any agent" generalization.
- deepseek-harness `cordis.yml` row mounting `notebook-mcp` (the dsh side; pairs with the CHIT/Cipher
  memory plugin — [[project_apps_as_mcp_plugins_architecture]]).
- `wealth-mcp` (Firefly) after the Firefly multi-tenancy A/B decision.

## Tenant / hazard notes
- The server is a thin stateless bridge reading ONE Notebook token; the per-tenant credential seam
  lives in the mounting harness (dsh `ctx.credentials` / A0 per-context header), not here.
- Open Notebook `surreal_data` dual-writer hazard — one writer per data path.
