# Create PMOVES Agent

Create a new PMOVES Agent instance with full ecosystem access.

## Arguments

- `$ARGUMENTS` - Agent role/specialization (e.g., "researcher", "code-reviewer", "media-processor")

## Prerequisites

Before creating agents, ensure:

1. **Submodules initialized:**
   ```bash
   git submodule update --init --recursive PMOVES-BoTZ
   ```

2. **Dependencies installed:**
   ```bash
   pip install -r pmoves/requirements.txt
   ```

3. **Services running:**
   ```bash
   # Check NATS
   curl http://localhost:4222

   # Check TensorZero
   curl http://localhost:3030/v1/models

   # Check Hi-RAG v2
   curl http://localhost:8086/healthz
   ```

## Instructions

1. Parse the agent role from arguments
2. Generate a unique agent ID using the pattern: `pmoves-{role}-{timestamp}`
3. Create agent configuration based on role:

### Available Roles

| Role | Description | Tools | Use Case |
|------|-------------|-------|----------|
| `researcher` | Deep research via SupaSerch + Hi-RAG | WebSearch, hirag_query, Task | Complex multi-source research |
| `code-reviewer` | Security-focused code analysis | Read, Grep, Glob | Code audits, PR reviews |
| `media-processor` | Video/audio analysis | Bash, Read, tensorzero_embed | Content processing |
| `knowledge-manager` | Hi-RAG knowledge operations | hirag_*, nats_publish | Knowledge base management |
| `general` | Full PMOVES access | All tools | General-purpose tasks |

### Agent Creation

```python
from pmoves_botz.features.agent_sdk import PMOVESAgent
import asyncio
from datetime import datetime

async def main():
    timestamp = int(datetime.now().timestamp())
    role = "researcher"  # Choose: researcher, code-reviewer, media-processor, knowledge-manager, general

    agent = PMOVESAgent(
        agent_id=f"pmoves-{role}-{timestamp}",
        role=role,
        model="openai::qwen3:8b",
    )

    await agent.connect()

asyncio.run(main())
```

4. Show created agent configuration:
   - Agent ID
   - Role and description
   - Available tools
   - MCP servers connected
   - Subagents available

5. NATS events published by agent:
   - `botz.agent.heartbeat.v1` - Agent presence (every 30s)
   - `agent.task.start.v1` - Task execution started
   - `botz.work.completed.v1` - Task completed successfully

## Example

```bash
/agent-sdk:create researcher
# Creates: pmoves-researcher-1735123456
# Tools: WebSearch, hirag_query, nats_publish, Task
# Subagents: None (top-level agent)
```
