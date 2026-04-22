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
| `honcho` | Session/memory management | **Overlap** — Cipher Memory (8105) |
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
| `honcho` | Cipher Memory (8105) | Prefer Cipher — Neo4j-backed, MCP-integrated |
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

## Recommended Deduplication Strategy

> **Policy:** PMOVES native services take priority over a0-plugins when capabilities overlap. Use a0-plugins only for gap-filling — capabilities that no native service provides.

### Decision Matrix

| Plugin | Native Alternative | Verdict | Rationale |
|--------|-------------------|---------|-----------|
| `honcho` | Cipher Memory (8105) | **Prefer native** | Cipher provides Neo4j-backed knowledge graphs, MCP integration, reasoning traces, and NATS event publishing (see [nats-subjects.md](../../.claude/context/nats-subjects.md#cipher-memory-subjects)). Honcho duplicates session/memory management without PMOVES observability. |
| `youtube_transcribe` | PMOVES.YT (8077) + FFmpeg-Whisper (8078) | **Prefer native** | PMOVES.YT offers full pipeline: download → MinIO storage → Whisper transcription → NATS events (`ingest.transcript.ready.v1`). Plugin only provides basic YouTube transcription without event-driven integration (see [services-catalog.md](../../.claude/context/services-catalog.md)). |
| `langfuse_observability` | TensorZero (3030) + ClickHouse | **Prefer native** | TensorZero is the canonical LLM observability layer — unified gateway for all model providers with ClickHouse-backed metrics, token tracking, and latency dashboards (see [observability-patterns.md](../../.claude/context/observability-patterns.md)). Langfuse adds a parallel observability stack with no integration to existing dashboards. |
| `discord` | Publisher-Discord (8094) | **Prefer native** | Publisher-Discord is NATS-integrated, subscribing to `ingest.file.added.v1`, `ingest.transcript.ready.v1`, and other events (see [nats-subjects.md](../../.claude/context/nats-subjects.md#media-ingestion-subjects)). The plugin provides direct Discord bot functionality but lacks event bus integration. |

### Gap-Filling Rule

Plugins that **do not** overlap with any native PMOVES service remain active and are encouraged:

- `agui_provider` — GUI provider (no native equivalent)
- `codex_provider` — Codex integration (no native equivalent)
- `linear` — Linear issue tracker (no native equivalent)
- `tree_sitter` — Code parsing (no native equivalent)
- `lazys_a0_marketplace` — Plugin marketplace UI (no native equivalent)
- `guard_system` — Partial overlap with BoTZ auth, but different scope (plugin-level vs gateway-level)
- `channels_provider` — Partial overlap with ClawZ, but serves Agent Zero's internal channel model
- `parallel_swarm` — Partial overlap with EvoSwarm, but operates within Agent Zero's runtime

### Review Cadence

- **Quarterly:** Re-evaluate overlap as new PMOVES services come online
- **On new plugin PR:** Check against `services-catalog.md` for overlap before merging
- **On new native service:** Review plugin catalog for newly-overlapping entries

### Migration Path

When a native service supersedes a plugin:
1. Document the overlap in this TAC tree
2. Update Agent Zero configuration to prefer the native service
3. Mark the plugin as `deprecated` in the catalog (do not remove — community may fork)
4. Add migration notes to the plugin's `index.yaml`

## Open Items

- ~~Plugin deduplication strategy needed — 4 plugins overlap with PMOVES native services~~ → **Resolved** (see [Recommended Deduplication Strategy](#recommended-deduplication-strategy) above)
- No runtime security sandboxing for plugins (plugins run in Agent Zero's process)
- Plugin ecosystem vs BoTZ Skills marketplace — need canonical strategy for which is primary
- No versioning mechanism for plugin compatibility
- No NATS event emission when plugins are loaded/executed
- Potential for CHIT attribution on plugin-executed actions

<!-- GRAPHITI_MARK: CLAUDE-OPUS::TAC-DEEP-DIVE::2026-03-15 -->
