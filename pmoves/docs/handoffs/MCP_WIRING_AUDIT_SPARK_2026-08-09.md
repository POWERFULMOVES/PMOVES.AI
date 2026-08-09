# HANDOFF 5090 → SPARK — PMOVES-wide MCP wiring audit (2026-08-09)

Operator directive (5090 session, 2026-08-09, refined same day): audit **all
PMOVES services with an MCP surface**, plus a **vendored-vs-forked inventory**
and a **recommendations gap analysis**. (MCP wiring is one reason forks exist,
not the sole one — the audit should say per-repo why we carry it and what the
integration actually buys.)

## The ask

1. **MCP surface inventory** — every PMOVES service and fork that ships an MCP
   surface: transport, auth, registration status. Close the gap between *"an
   MCP server exists in the tree"* and *"the fleet can actually call it."* An
   unwired MCP is inventory, not capability.
2. **Vendored vs forked list** — for each external dependency: is it vendored,
   forked (which branch model), or plain upstream? What PMOVES-specific value
   does the fork carry (hardening, MCP surface, integration patches)? Flag
   forks that could drop back to upstream and vendored copies that should be
   forks.
3. **Gap analysis + recommendations** — ranked: what to wire, what to retire,
   what to upstream, what to leave.

## The loadout frame (why this matters)

BoTZ Gateway is the **store/configure/manage** layer for capability; Cipher
can **load context tools** so a model rolls in and out with a working loadout.
The Danger Room runs succeeded *because* agents weren't dropped in cold and
handed tools that don't explain themselves — quite the opposite. Target state
is the Matrix armory: when Neo and Trinity go to get Morpheus, the setup and
orchestration happened **before** the drop. (Operator note: that scene is a
promo analogue worth producing once the Jetson combiner fleet is deployed.)
The audit's output feeds exactly that: a per-tool "what it does, how to call
it, what it needs" surface that BoTZ stores and Cipher serves.

## Known state at handoff (5090 observations, single-node)

| Surface | State | Notes |
|---|---|---|
| `pmoves-cipher` (`:8105`) | **wired + working** | `.claude/mcp.json` SSE entry; REST write path proven 2026-08-09: `POST /api/memory`, Bearer `CIPHER_API_TOKEN`, body needs `agentId` + `metadata.source ∈ [agent\|system\|user]`. BM25 hybrid search layer live (operator: "quick and also useful"). MCP tools only attach if cipher-api is UP at session start — it was down ~41h until 2026-08-09; consider a health-gated autostart. |
| `pmoves-jcodemunch-mcp` (n8n MCP, v1.108.64) | **present, UNWIRED** | Can create/adjust n8n workflows via the n8n Public API. Needs an `.claude/mcp.json` entry + `N8N_API_URL`/`N8N_API_KEY`. The API key comes from `make -C pmoves n8n-bootstrap`, which 401s until the owner password is reset (`n8n user-management:reset`, operator-gated). Check upstream (czlonkowski/n8n-mcp) drift while here. |
| `agent-zero` (`:8080/mcp`) | wired | mcp.json entry present; utility-command surface only. |
| `pmoves-nats-fleet` | wired | deferred-tool validation carry-over lives in `handoff_5090_next_session_mcp_fleet_validation`. |
| `pmoves-hirag-mcp` | **unknown** | stdio bridge scaffolded by COWORK-CLAUDE (register 2026-06-11); verify it's registered anywhere. |
| `pmoves-supabase`, `docker`, `hostinger`, `tailscale`, `cloudflare`, `huggingface` | wired | external/infra MCPs, not fork surfaces. |
| Other forks (BoTZ gateway, Archon, Pipecat, DoX, …) | **inventory unknown** | This is the bulk of the audit: which forks ship MCP servers, which are registered in `.claude/mcp.json` / `pmoves_5090_web` OCI profile / per-node profiles, which are dead code. |

## Suggested shape

1. Inventory: grep forks for MCP entrypoints (`mcp.json`, `FastMCP`, `mcp.server`,
   `@modelcontextprotocol`, SSE `/sse` routes) → table of surface × transport ×
   auth × registration status.
2. Wire the gaps: per-node `.claude/mcp.json` entries (or the docker mcp profile
   road — see `project_pmoves_5090_web_profile_origin`), secrets via the
   env.tier→secrets-funnel pipeline ONLY.
3. Register outcomes in the docker MCP catalog/profile so every node inherits.
4. Living doc: record the resulting matrix where the fleet can find it
   (`.claude/context/mcp-api.md` is currently Agent-Zero-only).

Related flag (separate lane, task #12 on 5090): flute_pipecat hand-rolls a
WebSocket transport that upstream pipecat now ships with origin-restriction +
shutdown-stall fixes — same re-types-instead-of-names class.

Three-body: delivery=SPARK, control=DARKXSIDE, memory=this doc + the audit's
resulting matrix. Not claimed by 5090 — SPARK CLAIMs on pickup.
