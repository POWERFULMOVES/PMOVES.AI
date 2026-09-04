# PMOVES dsh (deepseek-harness) config

`pmoves.cordis.patch.yml` mounts the PMOVES MCP servers into **deepseek-harness (dsh)** as
native tools, so any dsh agent can use them — the "mount twice" half of build-once-mount-twice
(Agent Zero is the first mount; see `project_apps_as_mcp_plugins_architecture`).

## What it mounts

| Server | dsh tools | Transport |
|---|---|---|
| **cipher** | `mcp__cipher__pmoves_cipher_store` / `_search` / `_session_save` / `_session_recall` / `_store_reasoning` / `_reasoning_patterns` / `_hybrid_search` / `_graph_expand` / `_mcp_list` / `_mcp_get` | streamable-http `…/mcp` + `Bearer ${CIPHER_API_TOKEN}` |
| **notebook** | `mcp__notebook__save_note` / `search_notes` | streamable-http `…/mcp` |

This is **PMOVES.AI_INTEGRATION.md pending item #2** — the CHIT/Cipher memory seam mounts as
a cordis plugin beside the others (dsh has no privileged core). The streamable-http `/mcp`
transport + `Bearer` auth is the exact shape **verified live against Agent Zero** on the 5090
(cipher store→recall similarity 1.0; notebook save_note persisted) — PMOVES.AI #2910 (notebook),
#2919/#2923 (cipher), Pmoves-cipher#17 (the stateless `/mcp` endpoint).

## Apply

dsh loads bundles from its workspace, then the profile's `cordis.patch.yml`, then the home-level
one, then any `--patch` overlay. Point dsh at this file as the `--patch` overlay:

```bash
dsh --profile web --patch <path-to>/pmoves/config/dsh/pmoves.cordis.patch.yml
# inspect the assembled tree:
dsh --profile web --patch <…>/pmoves.cordis.patch.yml --dump-config
```

Env it reads (per process / per tenant — the tenant seam):
- `CIPHER_API_TOKEN` — required (Cipher 401s without it)
- `CIPHER_MCP_HTTP_URL` — optional override (default `http://cipher-api:8105/mcp`)
- `NOTEBOOK_MCP_URL` — optional override (default `http://notebook-mcp:8092/mcp`)

## Status (2026-09-04)

**Config-ready, not yet verified live in dsh.** dsh is a self-declared dev-preview (`sync:false`,
web UI :3080) and is **not currently running as a fleet service** — so this mount is authored to
the proven recipe (`packages/mcp/mcp-client/README.md`) and reuses transports verified against A0,
but the end-to-end `dsh → cipher` proof waits on standing dsh up. That deploy is a separate lane.
Recipe + field reference: `PMOVES-deepseek-harness/packages/mcp/mcp-client/README.md`.
