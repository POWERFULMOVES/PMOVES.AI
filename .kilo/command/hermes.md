# HERMES Agent — PMOVES Fleet Integration

HERMES Agent (Nous Research) integration with the PMOVES fleet. HERMES provides the autonomous agent loop; MiniMax or GLM provide the inference.

## HERMES ↔ MiniMax Setup

```bash
# Install HERMES (Linux/macOS/WSL2)
curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh | bash

# Configure HERMES to use MiniMax
hermes model
# → Select "MiniMax (International)" → enter MINIMAX_API_KEY

# Verify HERMES + MiniMax
hermes chat --provider minimax "ping" && echo "HERMES + MiniMax: OK"
```

## HERMES ↔ GLM (Z.AI) Setup

```bash
hermes model
# → Select "Z.AI" → enter Z_AI_API_KEY

hermes chat --provider zai "ping" && echo "HERMES + Z.AI: OK"
```

## PMOVES Fleet MCP Integration

HERMES can connect to PMOVES MCP servers:

```bash
# ~/.hermes/config.yaml — add these MCP servers
mcp_servers:
  pmoves-botz:
    url: "http://pmoves-botz:8090/mcp"
    headers:
      Authorization: "Bearer ${BOTZ_API_KEY}"
    enabled: true

  pmoves-hirag:
    url: "http://pmoves-hirag:8086/mcp"
    headers:
      Authorization: "Bearer ${HIRAG_API_KEY}"
    enabled: true

  pmoves-tensorzero:
    url: "http://pmoves-tensorzero:3030/mcp"
    headers:
      Authorization: "Bearer ${TENSORZERO_API_KEY}"
    enabled: true
```

## HERMES Health

```bash
# HERMES gateway status
hermes status

# Check loaded skills
hermes skills list

# Check memory
hermes memory search "minimax" 2>/dev/null || hermes chat "what do you remember about minimax"

# HERMES ↔ NATS mesh (fleet status)
nats sub "mesh.minimax.>" --server nats://localhost:4222 2>/dev/null &
nats sub "mesh.gpu.status.>" --server nats://localhost:4222 2>/dev/null &
```

## HERMES ↔ PMOVES Agent-Zero

HERMES can operate as a subordinate agent under PMOVES-Agent-Zero:

```bash
# Start HERMES as subordinate (fleet mode)
hermes chat --profile pmoves-fleet

# Verify NATS connectivity
nats pub mesh.minimax.status.v1 '{"hermes": "online", "model": "MiniMax-M2.7"}' \
  --server nats://localhost:4222
```

## Skill Creation for MiniMax

```bash
# Create a MiniMax-specific skill
hermes skills create minimax-wave-collapse << 'EOF'
# Skill: minimax-wave-collapse
Wave-function collapse reasoning using MiniMax M2.7.
When asked to analyze multiple paths or states, use wave-collapse:
1. Enumerate all possible states
2. Assign probability amplitudes
3. Collapse to most probable outcome
4. Report confidence
EOF

# Use the skill
hermes chat "use minimax-wave-collapse to analyze: building a coding agent vs a chat agent"
```

## Environment Variables

```bash
MINIMAX_API_KEY          # MiniMax token plan
MINIMAX_API_BASE        # https://api.minimax.io/v1 or China alternate
Z_AI_API_KEY            # Z.AI GLM coding plan
BOTZ_API_KEY            # PMOVES-BoTZ MCP access
HIRAG_API_KEY           # Hi-RAG MCP access
TENSORZERO_API_KEY     # TensorZero MCP access
HERMES_HOME             # ~/.hermes (default)
```

## References

- pmoves/docs/AGENTS/HERMES_INTEGRATION.md
- pmoves/docs/AGENTS/MINIMAX_INTEGRATION.md
- pmoves/configs/agent-profiles/minimax_claw.yaml
- https://hermes-agent.nousresearch.com/docs