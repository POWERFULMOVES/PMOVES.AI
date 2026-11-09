# HERMES ↔ MiniMax Integration — PMOVES.AI

**Last Updated:** 2026-05-18  
**Status:** `IN_PROGRESS`  
**HERMES:** v1+ (Nous Research)  
**MiniMax:** M2.7 / M2.1 (Token Plan + Local)

---

## Overview

HERMES Agent (Nous Research) is a self-improving autonomous agent with persistent memory, skill creation, and a messaging gateway across 20+ platforms. MiniMax M2.7 is a fast inference model with 1M token context and wave-function collapse reasoning. This document describes how they integrate at the PMOVES fleet level.

> *"HERMES provides the loop. MiniMax provides the inference. Together they form a self-improving, long-context reasoning system."*

```
┌────────────────────────────────────────────────────────────┐
│                    HERMES Agent (Nous)                       │
│  Memory · Skills · Delegation · Cron · Messaging Gateway   │
│                          │                                   │
│                    Model Provider                           │
│                          ▼                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │  MiniMax     │  │  Local      │  │  TensorZero  │    │
│  │  Cloud API  │  │  Ollama/ROCm │  │  Router      │    │
│  │  (Primary)  │  │  (Fallback) │  │  (Orchestra) │    │
│  └──────────────┘  └──────────────┘  └──────────────┘    │
└────────────────────────────────────────────────────────────┘
```

---

## Why This Matters for PMOVES

### The Hybrid Problem

PMOVES runs a heterogeneous fleet:
- **Cloud:** MiniMax token plan, Z.AI GLM, OpenAI
- **Local GPU:** ROCm (R9700), DGX Spark (GB10), 5090 (Ollama)
- **Local CPU:** VPS/cloud instances

HERMES needs to reach all of these. The integration maps HERMES' provider interface to PMOVES' fleet topology.

### Current State

| Component | Status | Notes |
|---|---|---|
| HERMES MiniMax OAuth | ✅ Supported | No API key needed, browser OAuth |
| HERMES MiniMax API key | ✅ Supported | `MINIMAX_API_KEY` env var |
| HERMES Nous Portal | ✅ Supported | Zero-config OAuth |
| HERMES TensorZero routing | 🔜 Planned | Requires PMOVES TensorZero MCP bridge |
| HERMES PMOVES fleet MCP | 🔜 Planned | PMOVES-BoTZ as MCP server |
| HERMES local ROCm | 🔜 Planned | Via OpenAI-compatible endpoint |
| HERMES local Spark | 🔜 Planned | Via Ollama ARM64 endpoint |

---

## Integration Paths

### Path 1: MiniMax Cloud API (Primary)

```yaml
# ~/.hermes/config.yaml
providers:
  minimax:
    type: openai-compatible
    name: MiniMax-M2.7
    api_key: "${MINIMAX_API_KEY}"
    base_url: "https://api.minimax.chat/v1"
    models:
      - MiniMax-M2.7      # 1M token context, primary
      - MiniMax-M2.1      # 100K context, efficient fallback
    model: MiniMax-M2.7
```

**HERMES command:**
```
hermes model
# → Select "MiniMax (International)" or "MiniMax (OAuth)"
```

**Environment:**
```bash
export MINIMAX_API_KEY=your_key_here
export MINIMAX_API_BASE=https://api.minimax.chat/v1  # or China variant
```

### Path 2: Nous Portal (OAuth — Zero Config)

```yaml
providers:
  nous_portal:
    type: nous-portal
    auth: oauth  # Device code OAuth via hermes model
```

```
hermes model
# → Select "Nous Portal" → browser OAuth → done
```

### Path 3: Local ROCm (Fallback)

When MiniMax cloud is unavailable, HERMES falls back to local ROCm inference:

```yaml
providers:
  llamacpp_rocm:
    type: openai-compatible
    name: Gemma-4-31B-ROCm
    api_key: "${LLAMACPP_ROCM_API_KEY}"
    base_url: "http://pmoves-rdna4:8080/v1"
    models:
      - gemma-4-31b-it-Q4_K_M.gguf
    model: gemma-4-31b-it-Q4_K_M.gguf
```

### Path 4: Local Spark Ollama (Fallback)

```yaml
providers:
  ollama_spark:
    type: openai-compatible
    name: Gemma-4-31B-Spark
    api_key: "${OLLAMA_SPARK_API_KEY}"
    base_url: "http://pmoves-spark:11434/v1"
    models:
      - gemma4:31b
    model: gemma4:31b
```

---

## MCP Integration

HERMES connects to MCP servers. PMOVES exposes several MCP endpoints that HERMES can use:

### BoTZ Framework MCP

PMOVES-BoTZ exposes a tool API that HERMES can consume as an MCP client:

```yaml
# ~/.hermes/config.yaml
mcp_servers:
  botz:
    url: "http://pmoves-9850x3d-r9700:8090/mcp"  # BoTZ MCP endpoint
    headers:
      Authorization: "Bearer ${BOTZ_API_KEY}"
    enabled: true
    tools:
      # Expose only BoTZ routing tools
      - route_model
      - botz_affinity
      - wave_status
```

### Hi-RAG MCP

```yaml
mcp_servers:
  hirag:
    url: "http://pmoves-hirag:8086/mcp"
    headers:
      Authorization: "Bearer ${HIRAG_API_KEY}"
    enabled: true
    tools:
      - search
      - recall
      - index_document
```

### TensorZero MCP

```yaml
mcp_servers:
  tensorzero:
    url: "http://pmoves-tensorzero:3030/mcp"
    headers:
      Authorization: "Bearer ${TENSORZERO_API_KEY}"
    enabled: true
    tools:
      - route
      - log_inference
      - get_routing_table
```

---

## PMOVES Fleet NATS Integration

HERMES can publish and subscribe to the PMOVES fleet event bus via NATS:

```bash
# HERMES hooks — post to NATS on tool execution
hermes hooks add --name pmoves-nats \
  --trigger tool_complete \
  --action "curl -s -X POST http://pmoves-nats:4222/mesh.minimax.wave.v1 \
    -H 'Content-Type: application/json' \
    -d '{\"agent\": \"hermes\", \"tool\": \"${TOOL}\", \"result\": \"${RESULT}\"}'"
```

### Relevant NATS Subjects

| Subject | Direction | Purpose |
|---|---|---|
| `mesh.minimax.wave.v1` | Subscribe | Wave-function collapse events |
| `mesh.minimax.status.v1` | Subscribe/Publish | MiniMax health + status |
| `mesh.minimax.model.loaded.v1` | Subscribe | Model load events |
| `mesh.gpu.command.v1` | Subscribe | GPU command dispatch |
| `mesh.gpu.status.v1` | Publish | GPU status announcements |
| `tokenism.signal.new.v1` | Subscribe | Tokenism signal events |

---

## PMOVES-BoTZ Affinity Matrix

HERMES tasks route to MiniMax based on BoTZ affinity:

| Task Type | Primary | Affinity | Fallback |
|---|---|---|---|
| Long-context research (>100K tokens) | MiniMax-M2.7 | High | GLM-5.1 |
| Wave-function collapse analysis | MiniMax-M2.7 | High | Gemma-4-31B |
| Coding overflow (GLM primary) | MiniMax-M2.1 | Medium | Qwen3-Coder |
| Hyperdimensional ops | MiniMax-M2.7 | High | Local ROCm |
| Standard chat / productivity | MiniMax-M2.1 | Medium | Nous Portal |
| Real-time messaging (<500ms SLA) | MiniMax-M2.1 | High | Local Spark |
| Skill creation (HERMES loop) | Nous Portal / MiniMax-M2.7 | Both | GLM |

---

## Health & Monitoring

### HERMES Health Commands

```bash
# MiniMax cloud status
curl -sf https://api.minimax.chat/v1/models \
  -H "Authorization: Bearer $MINIMAX_API_KEY"

# Local ROCm llama-server
curl -sf http://pmoves-rdna4:8080/v1/models

# Local Spark Ollama
curl -sf http://pmoves-spark:11434/v1/models

# HERMES ↔ MiniMax connection test
hermes chat --provider minimax "ping" && echo "MiniMax reachable"
```

### PMOVES Fleet Health

```bash
# HERMES gateway health
curl -sf http://localhost:3030/api/status | jq '.minimax'

# TensorZero routing
curl -sf http://localhost:3030/api/routing | jq '.minimax'

# NATS mesh
nats sub "mesh.minimax.>" --server nats://localhost:4222
```

---

## Skill Translation

HERMES skills are portable `.md` files. MiniMax-compatible skills follow the same interface:

```
skills/
├── pmoves-minimax-wave-collapse.md    # Wave-function collapse skill
├── pmoves-minimax-long-context.md     # 1M context research skill
├── pmoves-minimax-agent-teams.md      # Multi-agent coordination
├── pmoves-minimax-hyperdimensions.md # Hyperdimensional ops skill
├── pmoves-hermes-skill-bridge.md      # HERMES → PMOVES skill funnel
```

### Skill Loading

```bash
# HERMES loads skills from ~/.hermes/skills/
# PMOVES skills symlinked:
ln -s /root/.openclaw/workspace/PMOVES.AI/pmoves/skills/hermes-bridge/*.md \
  ~/.hermes/skills/

hermes skills list  # Shows PMOVES skills
```

---

## Agent Zero Integration

HERMES can operate as a subordinate agent under PMOVES-Agent-Zero:

```yaml
agent_zero:
  subordinate: true
  profile: hermes_minimax
  model: MiniMax-M2.7
  inherit_context: true
  report_to: agent_zero
  # HERMES publishes completed tasks to NATS
  nats_publish: mesh.minimax.task.complete.v1
```

### Workflow

```
Agent-Zero (orchestrator)
    │ "Research this codebase architecture"
    ▼
HERMES + MiniMax (worker)
    │ Executes HERMES skill loop
    │ Tool calls → MiniMax M2 reasoning
    │ Memory persists across sessions
    ▼
Result → NATS mesh.gpu.command.result.v1
    │
    ▼
Agent-Zero (control)
```

---

## Configuration Checklist

- [ ] `MINIMAX_API_KEY` set in environment
- [ ] `MINIMAX_API_BASE` set (cloud or China endpoint)
- [ ] HERMES provider configured (`hermes model` → MiniMax)
- [ ] NATS mesh reachable from HERMES host
- [ ] PMOVES-BoTZ MCP server accessible (if using BoTZ tools)
- [ ] Local inference fallbacks tested:
  - [ ] ROCm llama-server (`curl http://pmoves-rdna4:8080/v1/models`)
  - [ ] Spark Ollama (`curl http://pmoves-spark:11434/v1/models`)
- [ ] HERMES ↔ TensorZero MCP bridge configured (if using TZ routing)

---

## References

- [HERMES Agent Docs](https://hermes-agent.nousresearch.com/docs)
- [HERMES MCP Integration](https://hermes-agent.nousresearch.com/docs/user-guide/features/mcp)
- [MiniMax Integration](pmoves/docs/MINIMAX_INTEGRATION.md)
- [MiniMax Claude Parity Map](../AGENTS/MINIMAX_CLAUDE_PARITY_MAP.md)
- [BoTZ Framework](../AGENTS/AGNOTE4482.md)
- [Provider Catalog](../../config/provider_catalog.yaml)
- [TensorZero MiniMax Config](../../config/tensorzero/tensorzero.minimax.toml)

---

## GRAPHITI_MARK

`MINIMAX-HERMES::INTEGRATION::2026-05-18`