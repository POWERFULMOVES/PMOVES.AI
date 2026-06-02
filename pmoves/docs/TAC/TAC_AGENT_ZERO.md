# TAC Tree: Agent Zero

> Technology-Architecture-Context tree for the Agent Zero control-plane orchestrator — the primary L1 coordinator with embedded agent runtime and MCP API.

## Service Identity

| Field | Value |
|-------|-------|
| **Service** | Agent Zero |
| **Ports** | 8080 (API), 8081 (UI) |
| **Health** | `GET /healthz`, `GET /mcp/health` |
| **Metrics** | `GET /metrics` |
| **Submodule** | [`PMOVES-Agent-Zero`](../../PMOVES-Agent-Zero/) |
| **Docker Profile** | `agents` |
| **Tier** | agent |
| **Class** | Standard |
| **Evolution** | Mega |

## Upstream Dependencies

| Dependency | Type | Required |
|------------|------|----------|
| TensorZero (3030) | LLM gateway for agent conversations | Yes |
| NATS (4222) | Event bus for task coordination and mesh announcements | Yes |
| Supabase PostgREST (3010) | Persistent state and context storage | Yes |
| Cipher Memory (8105) | Agent plan/checkpoint/completion persistence | Yes |
| Neo4j (7474) | Knowledge graph queries | Optional |
| Qdrant (6333) | Semantic search for agent context | Optional |

## Downstream Consumers

| Consumer | Interface | Description |
|----------|-----------|-------------|
| Archon (8091) | MCP API | Agent coordination via `/mcp/*` endpoints |
| BoTZ Gateway (8054) | MCP Gateway (:2091) | Skill invocation and tool routing |
| ClawZ (planned) | NATS / MCP | Chat-to-agent task delegation |
| Mesh Agent | NATS | Receives `mesh.node.announce.v1` for host discovery |
| Claude Code CLI | MCP API | External agent integration |
| All services | NATS | Publishes `agent.tool.executed.v1` for observability |

## Key Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/healthz` | GET | Health check (no auth required) |
| `/metrics` | GET | Prometheus metrics |
| `/mcp/health` | GET | MCP subsystem health |
| `/mcp/execute` | POST | Execute an MCP command |
| `/mcp/task/<id>` | GET | Query task status |
| `/mcp/subordinate/create` | POST | Spawn a subordinate agent |
| Port 8081 | HTTP | Web UI for agent interaction |

## NATS Subjects

| Subject | Direction | Description |
|---------|-----------|-------------|
| `agent.tool.executed.v1` | Publishes | Tool execution events for observability |
| `mesh.node.announce.v1` | Subscribes | Host presence/capability announcements (every 15s) |
| `claude.code.tool.executed.v1` | Subscribes | Claude Code CLI tool events (observability) |

## CHIT Integration Status

| Capability | Status | Notes |
|------------|--------|-------|
| Delta sensitivity | Active | `delta_sensitive: true` |
| Kappa sensitivity | Active | `kappa_sensitive: true` |
| Hz sensitivity | Active | `hz_sensitive: true` |
| Swarm participant | Active | `swarm_participant: true` |
| Attribution gated | Active | `attribution_gated: true` — all 5 CHIT toggles enabled |
| CGP packet processing | Planned | Agent Zero aware of CGP events but not a generator |

## Production Audit Checklist

| Requirement | Status | Notes |
|-------------|--------|-------|
| `/healthz` endpoint | GREEN | Implemented (no auth required) |
| `/metrics` (Prometheus) | GREEN | Implemented |
| Auth (JWT/Bearer) | Partial | MCP requires `MCP_CLIENT_SECRET`; API has basic auth |
| Docker hardening | GREEN | Runs in `agents` profile |
| NATS auth | GREEN | Uses authenticated NATS connection |
| `env.shared` format | GREEN | No `export` syntax issues |
| Subordinate isolation | Partial | Sub-agents share host context — isolation via task scoping only |

## Subordinate Agent Model

Agent Zero operates as the **primary L1 orchestrator** using a hub-and-spoke pattern:

1. **Task Delegation:** Receives tasks via MCP API or NATS, decomposes into subtasks
2. **Subordinate Creation:** Spawns sub-agents via `/mcp/subordinate/create` with scoped permissions
3. **Checkpoint/Resume:** All agent state persists through Cipher Memory categories:
   - `agent_plan` — initial task decomposition
   - `agent_checkpoint` — mid-execution state snapshots
   - `agent_completion` — final results and artifacts
4. **Tool Routing:** Sub-agents access 100+ tools via BoTZ Gateway Agent MCP endpoint

### Resilience

| Property | Value |
|----------|-------|
| Context budget | Large (100K tokens) |
| Checkpoint frequency | Per-wave |
| Recovery strategy | `cipher_resumable` |
| Cipher categories | `agent_plan`, `agent_checkpoint`, `agent_completion` |

## Cross-Links

- **Submodule:** `PMOVES-Agent-Zero/`
- **MCP API Reference:** `.claude/context/agent-zero-orchestration.md`
- **Agent Registry:** `pmoves/config/agent_registry.yaml` → `agent_zero`
- **Resilience Patterns:** `pmoves/docs/AGENTS/AGENT_RESILIENCE_PATTERNS.md`
- **Integration Topology:** [`TAC_INTEGRATION_TOPOLOGY.md`](./TAC_INTEGRATION_TOPOLOGY.md)
- **BoTZ Gateway TAC:** [`TAC_BOTZ.md`](./TAC_BOTZ.md) — primary tool routing consumer
- **Cipher TAC:** [`TAC_CIPHER.md`](./TAC_CIPHER.md) — resilience backbone

## Open Items

- MCP API auth model needs hardening — currently relies on shared secret only
- Subordinate agent isolation is logical, not containerized
- NATS subject surface is minimal (1 publish, 2 subscribes) — could publish task lifecycle events
- No dedicated NATS subjects for task assignment/completion (uses HTTP MCP API)
- Integration with autoresearch for experiment delegation (planned)

<!-- GRAPHITI_MARK: CLAUDE-OPUS::TAC-DEEP-DIVE::2026-03-15 -->
