# Cowork Connector Map — SaaS → PMOVES Analogs

**Purpose:** The Cowork `engineering` and `productivity` plugins declare SaaS connectors (Slack, Linear, Notion, Datadog, PagerDuty, etc.). PMOVES self-hosts analogs for nearly all of them. This doc maps each declared connector to its PMOVES analog and the MCP surface (existing or needed) that wires it into Cowork.

> Context reviewed: `AGNOTE4482.md`, `AGNOTE4482_SITREP.md`, `.claude/BOOTSTRAP.md`, `.claude/CATALOG.md`. Per Integration Rule: leverage, don't duplicate.

## Mapping

| Plugin expects | PMOVES analog | MCP surface today | Cowork wiring |
|---|---|---|---|
| Slack | ClawZ (active Discord agent) + Publisher-Discord `:8094` | None (NATS events only: `ingest.*`, summary/chapter) | **Gap** — thin MCP bridge over ClawZ/NATS, or community Discord MCP |
| Linear / Asana / ClickUp / monday | Archon `:8091` (+ Dart already connected in Cowork) | Archon connects to Agent Zero MCP; no direct MCP of its own | Use **Dart MCP** (already connected) for tasks; Archon via Agent Zero `/mcp/*` |
| Atlassian (Jira/Confluence) | Repo living docs + Hi-RAG v2 `:8086/:8087` | Hi-RAG is HTTP only (`POST /hirag/query`) | **Gap** — thin MCP bridge (highest-value custom connector) |
| Notion | Open Notebook (SurrealDB) + Notebook Sync `:8095` | HTTP via `$OPEN_NOTEBOOK_API_URL` + token | Bridge via Hi-RAG MCP (same gap as above) |
| GitHub | GitHub itself (no analog needed) | `git` MCP already connected in Cowork; gh runners self-hosted | Done |
| PagerDuty | NATS alerts + Publisher-Discord; no incident tool | `pmoves-nats-fleet` MCP (stdio, `NATS_URL` → KVM4-2 hub) | Covered by NATS MCP for publish/subscribe |
| Datadog | Prometheus `:9090` / Grafana `:3000` / Loki `:3100` / TensorZero ClickHouse `:8123` | observability-mcp-servers wave merged 2026-04-22; Grafana also has an official MCP | Register existing server, or official `grafana-mcp` pointed at `:3000` |
| Gmail / Google Calendar | n/a (real Google account) | Connected in Cowork already | Done |

## Existing MCP entrypoints (`.claude/mcp.json`)

| Server | Transport | Notes |
|---|---|---|
| `pmoves-cipher` | SSE `http://localhost:8105/mcp/sse` | Memory — **addable to Cowork as a custom connector URL today** |
| Agent Zero | HTTP `http://localhost:8080/mcp/*` | Orchestration/task delegation — addable as custom connector |
| `pmoves-nats-fleet` | stdio (`pmoves-nats-mcp/nats_mcp/server.py`) | Fleet hub pub/sub (PR #1490) |
| `docker`, `hostinger-mcp`, `tailscale`, `cloudflare`, `hf-mcp-server` | stdio | Already declared; Hostinger + HF also connected in Cowork natively |
| 4090 D-Proxy SSE gateway | SSE | Requires `make mcp-4090-gateway-start` |

## Recommended custom connector (the one real gap)

**`pmoves-hirag-mcp`** — a thin FastMCP server exposing:

- `hirag_query(query, top_k, rerank)` → `POST :8086/hirag/query` (CPU) / `:8087` (GPU)
- `notebook_search(q)` → Open Notebook API
- `service_health(name)` → `/healthz` per CATALOG.md

This single bridge covers the Notion + Confluence + knowledge-search lanes. Discord/ClawZ bridge is the second candidate if Slack-style messaging from Cowork is wanted.

**Cowork side:** SSE/HTTP servers (Cipher, Agent Zero, the proposed Hi-RAG bridge) are added via Settings → Connectors → custom connector URL. stdio servers stay in `.claude/mcp.json` for Claude Code sessions.

## Protocol note

Per AGNOTE4482 Village Rule: before implementing `pmoves-hirag-mcp` in a PMOVES lane, claim it in `AGNOTE4482PHI.t1.md`, build against the existing service APIs (don't rebuild retrieval), and run `make -C pmoves sign-trail` at session end.

<!-- GRAPHITI_MARK: COWORK-CLAUDE::CONNECTOR-MAP::2026-06-11 -->
