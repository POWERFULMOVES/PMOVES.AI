# Cipher Reasoning

Store and retrieve reasoning traces and patterns in Cipher Memory.

## Instructions

Manage reasoning traces in Cipher Memory. Two modes:

### Store a reasoning trace

```bash
# Store reasoning via Cipher Memory API
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

### Retrieve reasoning patterns

```bash
# Search for reasoning patterns
curl -s "http://localhost:8096/api/memory/search?q=$PATTERN_QUERY&category=reasoning_trace&limit=5"
```

**Notes:**
- Also available via MCP tools: `pmoves_cipher_store_reasoning`, `pmoves_cipher_reasoning_patterns`
- Reasoning traces help agents learn from past decisions
- Patterns are indexed for similarity search
