# PMOVES-KIMI Bootstrap

**Flat foundation for Kimi Code CLI sessions inside PMOVES.AI.**

You are on a PMOVES.AI node (Z890 / 5090 / 4090 / KVM4-1 / KVM4-2 / KVM2 / Jetson / SPARK / Cloudflare Edge). Every node is a pore in the lattice — capacity-class, not expertise-lane. Run PMOVES to your physical capacity. Delegate across nodes via the paths below when a task exceeds your local reach.

## Emperor-CHIT-Humility — disclose at session start

Before editing or non-trivial work, state which you have vs missing:

- [ ] **Cipher MCP** reachable (`kimi mcp test pmoves-cipher` or `curl -sf http://localhost:8105/health`)
- [ ] **Docker MCP** reachable (`kimi mcp test docker`)
- [ ] **E2B MCP** reachable (`kimi mcp test pmoves-e2b`)
- [ ] **NATS fleet MCP** reachable (`kimi mcp test pmoves-nats-fleet`)
- [ ] **Supabase MCP** reachable (`kimi mcp test pmoves-supabase`)
- [ ] **Known Roads** loaded (table below)
- [ ] **CHIT passphrase** set (`$CHIT_PASSPHRASE`; unsigned fallback is acceptable in dev)
- [ ] **Node-peer visibility** (`make -C pmoves fleet-status`)
- [ ] **MCP/service catalog** loaded (see `.claude/CATALOG.md` when needed)

Missing items are not failures — they are operational facts. Disclose them. Never bluff awareness.

## Launch command

Always launch Kimi from the repo root with the PMOVES project configuration:

```bash
make -C pmoves kimi
```

This loads `.kimi/config.toml` and `.kimi/mcp.json` explicitly so your session uses PMOVES model aliases and MCP servers regardless of the user's `~/.kimi/` settings.

## Known Roads — dangerous ops route through Make targets

| Need | Known Road |
|------|------------|
| Start / restart services | `make -C pmoves up-<service>` (never `docker compose up` raw) |
| Apply secrets | `make -C pmoves secrets-funnel` (before any service start after env change) |
| Read-only health | `make -C pmoves health-quick` / `health-check-all` |
| Fleet view | `make -C pmoves fleet-status` (never raw `tailscale status` for public IPs) |
| CHIT-sign provenance | `make -C pmoves sign-trail SUMMARY=... AGENT=...` |
| Refresh living docs | `make -C pmoves docs-reconcile` |
| Launch this bootstrap | `make -C pmoves kimi` |
| Browser / computer use | `make -C pmoves surf-up` (needs `E2B_API_KEY` + `OPENAI_API_KEY`) |
| Danger Room desktop | `make -C pmoves danger-room-desktop-up` (needs `E2B_API_KEY`) |
| Build with fanfare | `make -C pmoves danger-room-build IMAGE=<image>` |
| Launch KiloCode GLM | `make -C pmoves kilo` (opens VS Code; needs KiloCode extension) |
| KiloCode operator home | `pmoves/docs/AGENTS/KILOCODE_OPERATOR_HOME.md` |

Full Known Roads catalog lives in `.claude/PATTERNS.md § Known Roads`. When a damage-control hook converts a raw `docker` / `netsh` / `gh workflow run` command to an `ask` prompt, that means a Make target already exists — use it.

## MCP Entrypoints (configured in `.kimi/mcp.json`)

| Server | Transport | Purpose |
|--------|-----------|---------|
| `pmoves-cipher` | SSE `http://localhost:8105/mcp/sse` | Persistent agent memory lookups + writes |
| `agent-zero` | HTTP `http://localhost:8080/mcp` | Agent Zero orchestrator |
| `docker` | stdio `mcp/docker` | Container inspection via local Docker socket |
| `pmoves-docker-gateway` | SSE `http://localhost:8090/sse` | Full Docker MCP Toolkit gateway (botz-gateway bridge); start with `make -C pmoves mcp-toolkit-gateway-start` |
| `pmoves-nats-fleet` | stdio `./pmoves-nats-mcp` | Cross-node NATS publish/subscribe |
| `pmoves-e2b` | stdio `@e2b/mcp-server` via `pmoves-e2b-mcp-server` fork | E2B sandbox code execution (E2B_API_KEY from secrets funnel) |
| `pmoves-supabase` | stdio `@supabase/mcp-server-postgrest@0.1.1` | Self-hosted PostgREST data-plane access |
| `huggingface` | stdio `@llmindset/hf-mcp-server` | Hub model/dataset/space search + Gradio execution |

## Botz Gateway

`botz-gateway` (`http://botz-gateway:8054`) currently exposes a REST management API and NATS subjects, not an MCP server. Use it for:

- Work item dispatch: `botz.work.assigned.v1`
- Heartbeats: `botz.instance.heartbeat.v1`
- REST API: `/v1/work-items`, `/v1/register`, `/v1/instances`

A future Phase 2 may add an MCP/SSE bridge; until then, prefer NATS or the REST API via `curl`/`httpx`.

## Cross-node delegation — three paths

| Path | When to use |
|------|-------------|
| **Agent Zero MCP** `POST http://localhost:8080/mcp/command` | Orchestration, task delegation, subordinate agent spawn |
| **A2A** `GET /.well-known/agent-card.json` (activate via `A0_SET_a2a_server_enabled=true`) | Peer discovery, task submission across nodes |
| **NATS** `agent.peer.heartbeat.v1` | Continuous peripheral observation of peer nodes |

No task requires all three — pick the narrowest path that delivers. When A2A is disabled (default), say so in your disclosure; don't pretend cross-node delegation is available.

## Model / agent selection

PMOVES runs multiple agents/models. Prefer:

- **Local default:** `pmoves/qwen3.5-35b` — good balance on 4090/5090 hardware.
- **Remote default (Moonshot key set):** `kimi-for-coding` or `kimi-k2.7-code` — best for multi-file edits.
- **Deep architecture/planning:** Kimi K2.7-code or `pmoves/hermes-v4-70b` (Spark).
- **Security/hardening review:** Hermes V4 70B or Kimi K2.7-code.
- **Agent Zero orchestration:** Agent Zero itself via MCP/A2A — do not replace it.
- **Claw ACP routing:** `PMOVES-ClawZ/acp-router` already maps `kimi` -> `agentId: "kimi"`.
- **Voice / persona tasks:** route through TensorZero and Agent Zero; no direct voice MCP in Phase 1.

## Where to look next

| You want | Load |
|----------|------|
| Service ports, URLs, health endpoints | `.claude/CATALOG.md` |
| Full Known Roads, dev patterns, CHIT, skill pairings | `.claude/PATTERNS.md` |
| Who's working on what right now | `pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md` § Active Claim Register |
| Cold-start orientation | `pmoves/docs/AGENTS/AGNOTE4482_SITREP.md` |
| Gateway pointers (audits, waves, Three-Body) | `pmoves/docs/AGENTS/AGNOTE4482.md` |
| Architecture-level thesis | `pmoves/docs/architecture/PMOVES_MOF_ARCHITECTURE.md` |

## Rules that survive every session

1. **Leverage existing services, don't rebuild.** Hi-RAG v2 for retrieval, NATS for events, MinIO via Presign for artifacts, Agent Zero `/mcp/*` for orchestration. The catalog exists.
2. **Test before PR.** `/test:pr` + document the Testing section. Docstring coverage ≥80% on new Python.
3. **Never raw docker / tailscale CLI** for operations with Make-target equivalents. The hooks will block and redirect.
4. **Village Rule.** No agent operates alone in production validation. Claim (AGNOTE4482PHI.t1), work, sign, release.
5. **Signing is optional locally, never skipped for session-end provenance.** `sign-trail` emits unsigned if `CHIT_PASSPHRASE` unset — that's fine in dev, still run it.
6. **Prefer the minimum task scope.** If you find adjacent cleanups, open a follow-up; don't expand the current claim.

## When context feels heavy

If this file is all you remember, you can still do the right thing:
- Ask "is there a Make target for this?" — if yes, use it.
- Ask "is this file in `.claude/CATALOG.md` or `.claude/PATTERNS.md`?" — if yes, load it.
- Ask "have I disclosed what I don't know?" — if no, do that first.

The rest is scaffolding.
