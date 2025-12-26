# Run PMOVES Agent

Execute a task using a PMOVES Agent with full ecosystem access.

## Prerequisites

Before running agents, ensure:

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

4. **Agent created:**
   ```bash
   pmoves agent-sdk list  # Verify agent exists
   ```

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
- ✅ Publishes events: `botz.agent.heartbeat.v1`, `agent.task.start.v1`, `botz.work.completed.v1`
- ✅ Returns structured results

## Model Selection

The agent uses TensorZero with dynamic model routing:

| Task Type | Default Model | Override |
|-----------|---------------|----------|
| Simple queries | `openai::qwen3:8b` | Local Ollama |
| Complex reasoning | `anthropic::claude-sonnet-4-5` | Cloud |
| Embeddings | `openai::nomic-embed-text` | Local |

## Timeouts

- **Task execution:** 300 seconds (5 minutes) default
- **HTTP requests:** 30 seconds
- **NATS connection:** 10 seconds

Configure via environment variables:
```bash
export AGENT_TASK_TIMEOUT=300    # Task timeout in seconds
export AGENT_HTTP_TIMEOUT=30     # HTTP timeout in seconds
export AGENT_NATS_TIMEOUT=10     # NATS connection timeout in seconds
```

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
- **Timeouts**: Long-running tasks may timeout. Break complex tasks into smaller steps.

## Troubleshooting

**"Agent not found"**
- Check agent exists: `pmoves agent-sdk list`
- Verify agent ID is correct (include timestamp)

**"Connection failed"**
- Check service health:
  ```bash
  curl http://localhost:4222  # NATS
  curl http://localhost:3030/healthz  # TensorZero
  curl http://localhost:8086/healthz  # Hi-RAG
  ```

**"Model not available"**
- Verify model is configured in TensorZero
- Check provider credentials (OpenAI, Anthropic, etc.)
- List available models: `curl http://localhost:3030/v1/models`

**"Task timed out"**
- Break task into smaller steps
- Increase timeout: `export AGENT_TASK_TIMEOUT=600`
- Check for infinite loops in tool calls
