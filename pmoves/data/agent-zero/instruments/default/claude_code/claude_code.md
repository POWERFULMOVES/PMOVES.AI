# Problem
Execute Claude Code CLI slash commands from Agent Zero for service interaction, health checks, and PMOVES operations.

# Solution
Use the Claude Code slash command system to interact with PMOVES production services.

## Available Slash Commands

### Search Commands
```bash
# Query Hi-RAG v2 hybrid retrieval (vector + graph + full-text)
# Prompt: Your search query
/search:hirag "<query>"

# Multimodal holographic deep research via SupaSerch
# Prompt: Research topic
/search:supaserch "<topic>"

# LLM-based research planning via DeepResearch
# Prompt: Research question
/search:deepresearch "<question>"
```

### Health Commands
```bash
# Verify all 55 PMOVES service health endpoints
/health:check-all

# Query Prometheus for metrics
# Prompt: PromQL query (optional)
/health:metrics [<promql>]
```

### Agent Commands
```bash
# Check Agent Zero orchestrator health
/agents:status

# Query Agent Zero MCP API
# Prompt: MCP query
/agents:mcp-query "<query>"
```

### Deploy Commands
```bash
# Run comprehensive smoke tests (75+ tests)
/deploy:smoke-test

# Check Docker Compose service status
/deploy:services

# Start services with docker compose
/deploy:up
```

### BoTZ Commands
```bash
# Run onboarding helper
# Args: --generate to create files
/botz:init [--generate]

# Hardware profile management
# Args: list, show <id>, detect, apply <id>, current
/botz:profile <action>

# MCP toolkit verification
# Args: list, health, setup <tool_id>
/botz:mcp <action>

# CHIT secret encode/decode
# Args: encode, decode
/botz:secrets <action>
```

## Implementation Pattern

Commands are markdown files in `.claude/commands/<category>/<name>.md` that contain:
1. Description of what the command does
2. Usage instructions
3. Implementation steps (bash commands, curl requests)
4. Notes and related commands

## Service Endpoints

Key PMOVES services accessible via commands:
- **Agent Zero**: 8080 (API), 8081 (UI)
- **Hi-RAG v2**: 8086 (CPU), 8087 (GPU)
- **SupaSerch**: 8099
- **DeepResearch**: 8098
- **TensorZero**: 3030 (LLM gateway)
- **Prometheus**: 9090
- **NATS**: 4222

## NATS Integration

Commands can publish/subscribe to NATS subjects:
- `claude.code.tool.executed.v1` - CLI tool events
- `research.deepresearch.request.v1` - Research requests
- `ingest.transcript.ready.v1` - Media transcripts

## Notes
- Commands directory: `/home/pmoves/PMOVES.AI/.claude/commands/`
- Context documentation: `/home/pmoves/PMOVES.AI/.claude/context/`
- Pre-tool hook blocks dangerous operations
- Post-tool hook publishes observability events to NATS
