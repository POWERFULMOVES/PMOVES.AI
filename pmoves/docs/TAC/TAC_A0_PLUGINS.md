# TAC Tree: a0-plugins

> Technology-Architecture-Context tree for the Agent Zero community plugin index — the curated registry of plugins visible to Agent Zero users.

## Service Identity

| Field | Value |
|-------|-------|
| **Service** | a0-plugins (Plugin Index) |
| **Port** | None (static index repository, not a service) |
| **Health** | N/A |
| **Metrics** | N/A |
| **Submodule** | `PMOVES-a0-plugins` |
| **Docker Profile** | N/A |
| **Tier** | agent (extension) |
| **Class** | Utility |
| **Evolution** | Base |

## Upstream Dependencies

| Dependency | Type | Required |
|------------|------|----------|
| Agent Zero (8080) | Plugin host — loads plugins dynamically | Yes |
| GitHub | Plugin source repositories | Yes |
| CI pipeline | Automated PR validation | Yes |

## Downstream Consumers

| Consumer | Interface | Description |
|----------|-----------|-------------|
| Agent Zero instances | Plugin loading | Dynamically load plugins at runtime |
| Plugin authors | PR submissions | Community plugin contributions |

## Key Endpoints

_None — a0-plugins is a static index repository._

## NATS Subjects

_None — plugins communicate through Agent Zero's runtime, not NATS directly._

## CHIT Integration Status

| Capability | Status | Notes |
|------------|--------|-------|
| CGP packet generation | None | Metadata index, not a processing service |
| Attribution | None | Plugin execution attribution handled by Agent Zero |

## Production Audit Checklist

| Requirement | Status | Notes |
|-------------|--------|-------|
| `/healthz` endpoint | N/A | Static repository |
| `/metrics` (Prometheus) | N/A | No runtime |
| Auth (JWT/Bearer) | N/A | GitHub-based access control |
| Docker hardening | N/A | Not containerized |
| NATS auth | N/A | No NATS integration |
| CI validation | GREEN | Automated PR validation pipeline |

## Plugin Catalog

13 community plugins + 1 example template (as of 2026-03-15):

| Plugin | Description | Overlap with PMOVES |
|--------|-------------|---------------------|
| `_example1` | Example template (reserved) | — |
| `agui_provider` | GUI provider for Agent Zero | — |
| `channels_provider` | Channel communication provider | Partial — ClawZ handles messaging |
| `codex_provider` | Codex integration provider | — |
| `discord` | Discord bot plugin | **Overlap** — Publisher-Discord (8094) |
| `guard_system` | Security guard system | Partial — BoTZ auth model |
| `honcho` | Session/memory management | **Overlap** — Cipher Memory (8096) |
| `langfuse_observability` | LLM observability | **Overlap** — TensorZero ClickHouse |
| `lazys_a0_marketplace` | Plugin marketplace UI | — |
| `linear` | Linear issue tracker integration | — |
| `parallel_swarm` | Parallel agent swarm execution | Partial — EvoSwarm Controller |
| `te_st1` | Test plugin | — |
| `tree_sitter` | Code parsing with tree-sitter | — |
| `youtube_transcribe` | YouTube video transcription | **Overlap** — PMOVES.YT (8077) |

### PMOVES Service Overlap Analysis

| Plugin | PMOVES Native Service | Recommendation |
|--------|----------------------|----------------|
| `honcho` | Cipher Memory (8096) | Prefer Cipher — Neo4j-backed, MCP-integrated |
| `youtube_transcribe` | PMOVES.YT (8077) + FFmpeg-Whisper (8078) | Prefer PMOVES.YT — full pipeline with NATS events |
| `langfuse_observability` | TensorZero (3030) + ClickHouse | Prefer TensorZero — unified observability |
| `discord` | Publisher-Discord (8094) | Prefer Publisher — integrated with NATS events |

## Plugin Submission Structure

```text
plugins/<plugin_name>/
├── index.yaml           # title, description, github URL, tags, screenshots
└── thumbnail.png        # Optional (square, ≤20KB)
```

### Validation Rules (CI-enforced)

- One plugin per PR
- Unique folder name: `^[a-z0-9_]+$`
- Required fields: `title` (≤50 chars), `description` (≤500 chars), `github` URL
- `github` URL must contain `plugin.yaml` with `name` matching folder name
- Optional: `tags` (≤5), `screenshots` (≤5 URLs, each ≤2MB)
- `index.yaml` total max: 2000 characters

## Cross-Links

- **Submodule:** `PMOVES-a0-plugins/`
- **Agent Zero TAC:** [`TAC_AGENT_ZERO.md`](./TAC_AGENT_ZERO.md) — plugin host
- **BoTZ TAC:** [`TAC_BOTZ.md`](./TAC_BOTZ.md) — skills marketplace (parallel ecosystem)
- **Cipher TAC:** [`TAC_CIPHER.md`](./TAC_CIPHER.md) — native alternative to `honcho` plugin
- **Integration Topology:** [`TAC_INTEGRATION_TOPOLOGY.md`](./TAC_INTEGRATION_TOPOLOGY.md)
- **Tags:** `PMOVES-a0-plugins/TAGS.md` — recommended tag list

## Open Items

- Plugin deduplication strategy needed — 4 plugins overlap with PMOVES native services
- No runtime security sandboxing for plugins (plugins run in Agent Zero's process)
- Plugin ecosystem vs BoTZ Skills marketplace — need canonical strategy for which is primary
- No versioning mechanism for plugin compatibility
- No NATS event emission when plugins are loaded/executed
- Potential for CHIT attribution on plugin-executed actions

<!-- GRAPHITI_MARK: CLAUDE-OPUS::TAC-DEEP-DIVE::2026-03-15 -->
