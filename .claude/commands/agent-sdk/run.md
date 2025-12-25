# Run PMOVES Agent

Execute a task using a PMOVES Agent with full ecosystem access.

## Usage

Use this command when:
- Running a task with an existing agent instance
- Executing code analysis, research, or media processing
- Streaming agent output with tool execution visibility

## Implementation

Execute via PMOVES CLI:

```bash
pmoves agent-sdk run <agent-id> <task>
# Execute task with streaming output

# With custom model:
pmoves agent-sdk run research-agent "Analyze PMOVES architecture" --model openai::gpt-4o

# Resume from session:
pmoves agent-sdk run research-agent "Continue analysis" --session session-abc123
```

### Arguments

- `agent-id` - Agent identifier (required)
- `task` - Task description to execute (required)

### Options

- `--model, -m` - Override model (default: agent's configured model)
- `--session` - Session ID to resume from

## What It Does

- ✅ Loads agent configuration and context
- ✅ Executes task with streaming output
- ✅ Shows tool usage in real-time
- ✅ Tracks execution metrics (tokens, duration, tools)
- ✅ Publishes completion event: `botz.work.completed.v1`
- ✅ Returns structured results

## Model Selection

The agent uses TensorZero with dynamic model routing:

| Task Type | Default Model | Override |
|-----------|---------------|----------|
| Simple queries | `openai::qwen3:8b` | Local Ollama |
| Complex reasoning | `anthropic::claude-sonnet-4-5-20250514` | Cloud |
| Embeddings | `openai::nomic-embed-text` | Local |

## Example

```bash
$ pmoves agent-sdk run pmoves-researcher-1735123456 "Analyze the authentication flow in services/gateway"

🎯 Executing task with 'pmoves-researcher-1735123456'...
📝 Task: Analyze the authentication flow in services/gateway

🔍 Searching for authentication-related files...
📖 Reading services/gateway/main.py...
🔧 Using: hirag_query
🤖 Based on my analysis, the authentication flow...

✅ Result: Analysis complete
📊 Metrics:
   - Tokens: 1,234
   - Duration: 12.5s
   - Tools: hirag_query, Read, Grep
```

## Related Commands

- `pmoves agent-sdk create` - Create new agent instance
- `pmoves agent-sdk list` - List all agents
- `pmoves agent-sdk status` - Check agent status
- `pmoves agent-sdk resume` - Resume existing session

## Notes

- **Agent ID Required**: Agent must be created first with `pmoves agent-sdk create`
- **Session Persistence**: Use `--session` to resume from previous checkpoint
- **Streaming Output**: Output streams in real-time as agent processes task
- **Event Bus**: Agent publishes events to NATS for observability

## Troubleshooting

**"Agent not found"**
- Check agent exists: `pmoves agent-sdk list`
- Verify agent ID is correct (include timestamp)

**"Connection failed"**
- Check service health:
  ```bash
  curl http://localhost:4222  # NATS
  curl http://localhost:3030/healthz  # TensorZero
  ```

**"Model not available"**
- Verify model is configured in TensorZero
- Check provider credentials (OpenAI, Anthropic, etc.)
