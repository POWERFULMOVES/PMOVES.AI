# Run PMOVES Agent

Execute a task using a PMOVES Agent with full ecosystem access.

## Arguments

- `$ARGUMENTS` - Task description to execute

## Instructions

1. Parse the task from arguments
2. If no active agent, create a general-purpose agent
3. Execute task with streaming output:

```python
from pmoves_botz.features.agent_sdk import PMOVESAgent

agent = PMOVESAgent(agent_id="pmoves-general-{timestamp}", role="general")
await agent.connect()

async for message in agent.execute(task="$ARGUMENTS"):
    if message.type == "assistant":
        print(message.content)
    elif message.type == "tool_use":
        print(f"Using tool: {message.tool_name}")
    elif message.type == "result":
        print(f"Result: {message.result}")
```

4. Track execution metrics:
   - Tools used
   - Token consumption
   - Duration
   - Subagent delegations

5. Publish completion event:
   ```
   Subject: botz.work.completed.v1
   Payload: {"agent_id": "...", "task": "...", "success": true, "metrics": {...}}
   ```

## Model Selection

The agent uses TensorZero with dynamic model routing:

| Task Type | Default Model | Override |
|-----------|---------------|----------|
| Simple queries | `openai::qwen3:8b` | Local Ollama |
| Complex reasoning | `anthropic::claude-sonnet-4-5-20250514` | Cloud |
| Embeddings | `openai::nomic-embed-text` | Local |

## Example

```bash
/agent-sdk:run "Analyze the authentication flow in services/gateway"
# Agent executes with full PMOVES access
# Uses Hi-RAG for context, Grep/Read for code analysis
# Returns structured analysis
```
