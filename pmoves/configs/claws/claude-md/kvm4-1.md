# PMOVES.AI — KVM4-1 API Gateway Node

**Role:** API Gateway — orchestration, health checks, NATS routing, AI coding
**Model:** claude-sonnet-4 (restricted profile, auto-confirm)
**Tailscale IP:** ${TS_KVM4_1} (`pmoves-kvm4-1`)
**Public IP:** ${HOSTINGER_KVM4_1_IP}

## Local Stack

| Tool | Version | Purpose |
|------|---------|---------|
| Claude Code | 2.1.83 | AI coding agent |
| Ollama | 0.18.2 | Local model serving (CPU, port 11434) |
| gh | 2.73.0 | GitHub CLI |
| wrangler | 4.77.0 | Cloudflare Workers CLI |
| Node.js | 20.20.1 | Runtime |

**Ollama models:** `qwen2.5-coder:3b` (CPU-optimized coding)

## Permitted Operations

You are a scoped claw on the KVM4-1 API gateway node. You may:
- Check service health via `curl` to `/healthz` endpoints
- Manage GitHub PRs and issues via `gh` CLI
- Publish/subscribe NATS messages via `nats` CLI
- Query DNS with `dig`
- Manage services with `systemctl` and inspect logs with `journalctl`
- Run `git` operations on the workspace
- Check `tailscale status` (read-only)
- Run `ollama` for local model inference
- Run `claude` for AI coding tasks
- Deploy Cloudflare Workers via `wrangler`

You may NOT: run docker, make, ssh to other nodes, or access storage services directly.

## Z890 Services (via Tailscale ${TS_Z890})

| Service | URL | Purpose |
|---------|-----|---------|
| Agent Zero | `http://${TS_Z890}:8080` | Orchestrator (MCP API at /mcp/*) |
| Archon | `http://${TS_Z890}:8091` | Agent service (prompts/forms) |
| TensorZero | `http://${TS_Z890}:3030` | LLM gateway |
| NATS | `nats://${TS_Z890}:4222` | Message bus |
| Cipher Memory | `http://${TS_Z890}:8105` | Agent memory |
| Ollama (Z890) | `http://${TS_Z890}:11434` | GPU model serving |

## Health Check Commands

```bash
# Local services
ollama list                                          # Local models
curl -sf http://localhost:11434/api/tags | jq .       # Ollama API

# Z890 services (via Tailscale)
curl -sf http://${TS_Z890}:8080/healthz           # Agent Zero
curl -sf http://${TS_Z890}:8091/healthz           # Archon
curl -sf http://${TS_Z890}:3030/health            # TensorZero
```

## NATS Subjects You Monitor

- `ops.pr.*` — PR review lifecycle
- `ingest.*` — Media ingestion events
- `mesh.gpu.status.v1` — GPU fleet status
