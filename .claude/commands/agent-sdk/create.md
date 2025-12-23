# Create PMOVES Agent

Create a new PMOVES Agent instance with full ecosystem access.

## Arguments

- `$ARGUMENTS` - Agent role/specialization (e.g., "researcher", "code-reviewer", "media-processor")

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

agent = PMOVESAgent(
    agent_id="pmoves-{role}-{timestamp}",
    role="{role}",
)
await agent.connect()
```

4. Show created agent configuration:
   - Agent ID
   - Role and description
   - Available tools
   - MCP servers connected
   - Subagents available

5. Announce agent on NATS:
   ```
   Subject: botz.agent.registered.v1
   Payload: {"agent_id": "...", "role": "...", "capabilities": [...]}
   ```

## Example

```bash
/agent-sdk:create researcher
# Creates: pmoves-researcher-1703123456
# Tools: WebSearch, hirag_query, nats_publish, Task
# Subagents: None (top-level agent)
```
