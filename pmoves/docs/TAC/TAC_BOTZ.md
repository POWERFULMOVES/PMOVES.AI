# TAC Tree: BoTZ

> Technology-Architecture-Context tree for the BoTZ skills marketplace framework.

## Service Identity

| Field | Value |
|-------|-------|
| **Service** | BoTZ Gateway |
| **Port** | 8054 (Gateway), 8100 (Gateway Agent), 2091 (MCP Gateway) |
| **Health** | `GET /healthz` |
| **Submodule** | `PMOVES-BoTZ` |
| **Docker Profile** | `agents` |
| **Tier** | agent |
| **Class** | Standard |
| **Evolution** | Stage 1 |

## Upstream Dependencies

| Dependency | Type | Required |
|------------|------|----------|
| TensorZero (3030) | LLM gateway for skill execution | Yes |
| NATS (4222) | Event bus for skill coordination | Yes |
| Supabase PostgREST (3010) | Skill registry + user data | Yes |
| Agent Zero (8080) | Orchestration control plane | Yes |
| Cipher Memory (8096) | Agent memory persistence | Optional |

## Downstream Consumers

| Consumer | Interface | Description |
|----------|-----------|-------------|
| Agent Zero | MCP Gateway (:2091) | Skill invocation via MCP |
| Archon | REST API | Form-driven skill execution |
| Claude Code CLI | Skill commands | `/botz:*` skill invocations |
| Docling (3020) | Document processing | PDF/document skill execution |
| VL Sentinel (7072) | Vision-language monitoring | Visual skill execution |
| E2B (7071) | Code execution sandbox | Sandboxed skill execution |

## Key Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/healthz` | GET | Health check |
| `/metrics` | GET | Prometheus metrics |
| MCP Gateway `:2091` | SSE | 100+ MCP tools for agent orchestration |

## NATS Subjects

| Subject | Direction | Description |
|---------|-----------|-------------|
| `botz.workitem.assigned.v1` | Publishes | Work item assigned to a BoTZ instance |
| `botz.work.available.v1` | Publishes | New work available for claiming |
| `botz.heartbeat.v1` | Subscribes | BoTZ CLI instance heartbeats |
| `botz.register.v1` | Subscribes | New BoTZ CLI instance registration |
| `botz.work.claimed.v1` | Subscribes | Work item claimed by instance |

## CHIT Integration Status

| Capability | Status | Notes |
|------------|--------|-------|
| CGP packet generation | Not active | `attribution_gated: false` |
| Swarm participant | Yes | `swarm_participant: true` |
| Delta/Kappa/Hz sensitivity | None | Not CHIT-sensitive yet |
| BPM capable | No | Skills are task-oriented, not prosodic |

## Production Audit Checklist

| Requirement | Status | Notes |
|-------------|--------|-------|
| `/healthz` endpoint | Partial | Gateway has it; MCP Gateway needs it |
| `/metrics` (Prometheus) | Yes | Implemented on Gateway |
| Auth (JWT/Bearer) | **P1 FAIL-OPEN** | `if not JWT_SECRET: return True` in `auth.py:59` |
| Docker hardening | Yes | `patterns.yaml` present |
| NATS auth | Yes | Uses authenticated NATS |
| `env.shared` format | **P1** | Uses `export` syntax (Docker-incompatible) |
| MCP Gateway auth | **P2** | Unauthenticated MCP endpoint |

## Security Stance (Phase C Audit)

| Finding | Severity | Status |
|---------|----------|--------|
| JWT fail-open (`if not JWT_SECRET: return True`) | P1 | **Open** — must fail-closed with HTTPException 500 |
| `export` syntax in env files | P1 | **Open** — use plain `KEY=VALUE` |
| MCP Gateway unauthenticated | P2 | **Open** — needs Bearer/API key auth |

## Tool Inventory

BoTZ exposes **100+ MCP tools** through the Gateway Agent, including:
- File operations, web search, code execution
- Docling document processing
- Cipher Memory queries
- VL Sentinel vision tasks
- E2B sandboxed execution

## Cross-Links

- **Submodule:** `PMOVES-BoTZ/`
- **Gateway Agent:** `PMOVES-BotZ-gateway/`
- **Integration Topology:** [`TAC_INTEGRATION_TOPOLOGY.md`](./TAC_INTEGRATION_TOPOLOGY.md)
- **Agent Registry:** `pmoves/config/agent_registry.yaml` → `botz_gateway`, `gateway_agent`
- **Audit Details:** `docs/submodules-audit-final-summary.md` → BoTZ section

## Open Items

- Auth bypass in `auth.py:59` — must fail-closed
- `env.shared` uses `export` syntax incompatible with Docker `env_file`
- MCP Gateway needs authentication layer
- Tool allowlisting for security-sensitive operations

<!-- GRAPHITI_MARK: CLAUDE-OPUS::TAC-TOPOLOGY-AUDIT::2026-02-20 -->
