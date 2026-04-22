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
| Cipher Memory (8105) | PostgREST API | Yes |

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
| Auth (JWT/Bearer) | **P1 FIXED** | `auth.py:63-67` now raises `HTTPException(500)` when `JWT_SECRET` is unset |
| Docker hardening | Yes | `patterns.yaml` present |
| NATS auth | Yes | Uses authenticated NATS |
| `env.shared` format | **P1 FIXED** | Stripped `export` prefix from `env.shared` (53 lines) and `env.tier-api` (21 lines) |
| MCP Gateway auth | **P2** | Unauthenticated MCP endpoint |

## Security Stance (Phase C Audit)

| Finding | Severity | Status |
|---------|----------|--------|
| JWT fail-open (`if not JWT_SECRET: return True`) | P1 | **Fixed** — `auth.py:63-67` now raises `HTTPException(500)` (fail-closed) |
| `export` syntax in env files | P1 | **Fixed** — stripped `export` prefix from `env.shared` and `env.tier-api` in BotZ-gateway submodule |
| MCP Gateway unauthenticated | P2 | **Open** — needs Bearer/API key auth |

## Tool Inventory

BoTZ exposes **100+ MCP tools** through the Gateway Agent, including:
- File operations, web search, code execution
- Docling document processing
- Cipher Memory queries
- VL Sentinel vision tasks
- E2B sandboxed execution

## Deep-Dive Findings (2026-03-15)

### Feature Modules

BoTZ Gateway comprises 17 feature modules spanning work distribution, CLI instance management, authentication, and MCP tool orchestration. The Gateway Agent (port 8100) exposes 100+ MCP tools through SSE transport on port 2091.

### Plugin Ecosystem Overlap

The a0-plugins index contains 4 plugins that overlap with PMOVES native services:
- `honcho` plugin vs Cipher Memory (8105) — Cipher is preferred (Neo4j-backed, MCP-integrated)
- `youtube_transcribe` vs PMOVES.YT (8077) — PMOVES.YT preferred (full pipeline with NATS)
- `discord` vs Publisher-Discord (8094) — Publisher preferred (NATS-integrated)
- `langfuse_observability` vs TensorZero (3030) — TensorZero preferred (unified observability)

**Strategy:** Prefer PMOVES native services for overlapping capabilities; use a0-plugins for gap-filling only.

### Security Hooks

BoTZ's `auth.py` implements JWT verification. The original fail-open vulnerability at line 59 has been **fixed** — `auth.py:63-67` now raises `HTTPException(status_code=500)` when `JWT_SECRET` is unset, ensuring fail-closed behavior.

## Cross-Links

- **Submodule:** `PMOVES-BoTZ/`
- **Gateway Agent:** `PMOVES-BotZ-gateway/`
- **Integration Topology:** [`TAC_INTEGRATION_TOPOLOGY.md`](./TAC_INTEGRATION_TOPOLOGY.md)
- **Agent Registry:** `pmoves/config/agent_registry.yaml` → `botz_gateway`, `gateway_agent`
- **Audit Details:** `docs/submodules-audit-final-summary.md` → BoTZ section
- **Agent Zero TAC:** [`TAC_AGENT_ZERO.md`](./TAC_AGENT_ZERO.md) — orchestration control plane
- **ClawZ TAC:** [`TAC_CLAWZ.md`](./TAC_CLAWZ.md) — chat gateway (different auth model)
- **a0-plugins TAC:** [`TAC_A0_PLUGINS.md`](./TAC_A0_PLUGINS.md) — plugin ecosystem overlap analysis
- **Cipher TAC:** [`TAC_CIPHER.md`](./TAC_CIPHER.md) — reasoning trace persistence

## Open Items

- ~~Auth bypass in `auth.py:59`~~ — **Fixed** (fail-closed via HTTPException 500)
- `env.shared` uses `export` syntax incompatible with Docker `env_file`
- MCP Gateway needs authentication layer
- Tool allowlisting for security-sensitive operations
- Plugin deduplication strategy with a0-plugins ecosystem
- ClawZ auth model alignment (DM pairing vs JWT)

<!-- GRAPHITI_MARK: CLAUDE-OPUS::TAC-DEEP-DIVE::2026-03-15 -->
