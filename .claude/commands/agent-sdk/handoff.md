# Handoff Task to Another Agent

Delegate a task to a specialized agent or local model worker.

## Arguments

- `$ARGUMENTS` - Task to delegate and optional target agent

## Instructions

1. Parse task and target from arguments
2. Determine best target agent based on task type:

### Handoff Targets

| Target | Use Case | Model |
|--------|----------|-------|
| `crush` | Local model work, routine tasks | Ollama via TensorZero |
| `researcher` | Deep research, multi-source | Cloud (Anthropic/Gemini) |
| `code-reviewer` | Code analysis, security review | Local or Cloud |
| `media-processor` | Video/audio processing | Local GPU |

### Handoff Protocol

```python
import nats

# Publish handoff request
await nats.publish("agent.handoff.request.v1", {
    "from": "claude-code",
    "to": "{target}",
    "task": "$ARGUMENTS",
    "context": {
        "files_read": [...],
        "current_dir": "...",
    },
    "reason": "specialized_task",
    "priority": 2,
})

# Wait for acceptance
response = await nats.request("agent.handoff.accepted.v1", timeout=30)

# Wait for completion
result = await nats.request("agent.handoff.completed.v1", timeout=300)
```

### NATS Subjects

| Subject | Direction | Purpose |
|---------|-----------|---------|
| `agent.handoff.request.v1` | Claude → Agent | Request delegation |
| `agent.handoff.accepted.v1` | Agent → Claude | Acknowledgment |
| `agent.handoff.completed.v1` | Agent → Claude | Result delivery |
| `agent.handoff.rejected.v1` | Agent → Claude | Unable to handle |

### Local Model Delegation

For routine tasks, delegate to PMOVES-Crush with local Ollama:

```python
# Check if task is suitable for local model
if is_routine_task(task):
    await nats.publish("crush.task.request.v1", {
        "task": task,
        "model": "openai::qwen3:8b",  # Local Ollama
        "max_tokens": 2048,
    })
```

## Example

```bash
/agent-sdk:handoff "Summarize this document" crush
# Delegates to PMOVES-Crush with local Qwen model
# Saves cloud API tokens for complex tasks

/agent-sdk:handoff "Research the latest RAG techniques" researcher
# Delegates to researcher subagent
# Uses Hi-RAG + SupaSerch + DeepResearch
```
