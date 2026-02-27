# Cipher Reasoning

Store and retrieve reasoning traces and patterns in Cipher Memory.

## Instructions

Manage reasoning traces in Cipher Memory. First check if the service is reachable.
If it is NOT reachable, fall back to local auto-memory.
Do NOT let a connection failure interrupt your workflow.

### Step 1: Health check (silent, non-blocking)

```bash
curl -sf --max-time 3 http://localhost:8096/health > /dev/null 2>&1 && echo "CIPHER_UP" || echo "CIPHER_DOWN"
```

### Store a reasoning trace

#### If CIPHER_UP:

```bash
curl -s -X POST http://localhost:8096/api/memory \
  -H "Content-Type: application/json" \
  -d '{
    "content": "$REASONING_CONTENT",
    "category": "reasoning_trace",
    "metadata": {
      "task": "$TASK_DESCRIPTION",
      "outcome": "$OUTCOME",
      "confidence": 0.85
    },
    "source": "claude-code",
    "timestamp": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"
  }'
```

#### If CIPHER_DOWN — Fallback:

Append the reasoning trace to your auto-memory file using the Write or Edit tool:
- File: `~/.claude/projects/<project>/memory/MEMORY.md`
- Add under a `## Reasoning Traces` section

### Retrieve reasoning patterns

#### If CIPHER_UP:

```bash
curl -s "http://localhost:8096/api/memory/search?q=$PATTERN_QUERY&category=reasoning_trace&limit=5"
```

#### If CIPHER_DOWN — Fallback:

Read the auto-memory file and search for reasoning-related entries.

**Notes:**
- Also available via MCP tools: `pmoves_cipher_store_reasoning`, `pmoves_cipher_reasoning_patterns`
- Reasoning traces help agents learn from past decisions
- Patterns are indexed for similarity search when Cipher is online
