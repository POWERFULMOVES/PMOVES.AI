# Claw Taxonomy Reference

## Bespoke Integration Principle

Each claw node is a bespoke integration — purpose-built for its hardware tier and agent workload. Claw configs are NOT one-size-fits-all; they encode node identity, exec policies, MCP topology, and model routing specific to that machine's role in the PMOVES.AI mesh.

## Provider Matrix

| Provider | Models | Config Key | Notes |
|----------|--------|------------|-------|
| Z.AI (GLM) | glm-5.1, glm-4.7, glm-4.5-air | `zai` | Primary — coding API at `api.z.ai` |
| Anthropic | claude-sonnet-4, claude-opus-4, claude-haiku-4-5 | `anthropic` | Sibling agent (claude-code) |
| OpenAI | gpt-4o, gpt-4o-mini | `openai` | TensorZero routing |
| Local (Ollama) | varies by GPU node | `ollama` | 5090, Jetson nodes |

## Claw Nodes

| Node | Role | GPU | Primary Model | Services |
|------|------|-----|---------------|----------|
| 5090 | GPU inference | RTX 5090 | glm-5.1 / claude-sonnet-4 | ollama, agent-zero, tensorzero, nats |
| Z890 | Knowledge + orchestration | — | claude-sonnet-4 | cipher, archon, nats, neo4j |
| Jetson | Edge inference | Orin | local (quantized) | ollama, tensorzero |

## PMOVES.Flare Namespace Convention

Claw configs live under `pmoves/configs/claws/` and follow this structure:

```
pmoves/configs/claws/
  scopes/
    <node>.json          # Node-level claw identity + MCP + exec policies
  opencode-<node>.json   # OpenClaw-specific mode + model overrides
```

Config files use the `PMOVES.Flare` namespace pattern:
- `pmoves-cipher` — Cipher memory MCP
- `pmoves-*` — PMOVES-branded service integrations
- `zai-*` — Z.AI provider integrations
- Agent-tool MCP servers use short lowercase names (e.g., `docker`, `filesystem`)

## Integration Points

- **kilo.json**: Project-level agent config, MCP server registry, context paths
- **scopes/<node>.json**: Per-node claw identity, exec allowlists, MCP topology
- **opencode-<node>.json**: OpenClaw mode bindings, model overrides, service ports
- **.kilo/command/**: Operator slash commands for agent workflows
- **.kilo/agent/**: Agent persona definitions
