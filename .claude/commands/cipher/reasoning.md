# Cipher Reasoning

Store and retrieve reasoning traces and patterns in Cipher Memory.

## Instructions

Manage reasoning traces in Cipher Memory. Use MCP tools as the primary path.
If Cipher is unreachable or MCP fails, fall back to local auto-memory.
Do NOT let a connection failure interrupt your workflow.

### Step 1: Health check (silent, non-blocking)

```bash
curl -sf --max-time 3 http://localhost:8096/health > /dev/null 2>&1 && echo "CIPHER_UP" || echo "CIPHER_DOWN"
```

---

### Store a reasoning trace

#### Primary: MCP tool (if CIPHER_UP)

Use the MCP tool `pmoves_cipher_store_reasoning`:

```
Tool: pmoves_cipher_store_reasoning
Arguments:
  question: "$QUESTION"
  reasoning: "$CHAIN_OF_THOUGHT"
  result: "$FINAL_ANSWER"
  metadata: { "task": "$TASK", "confidence": 0.85 }
```

> **Known issue (2026-04-01):** MCP tools are currently blocked by the same gap as REST.
> The MCP client (`pmoves-cipher-mcp/cipher_mcp/client.py`) calls `/api/memory` endpoints
> which do not exist in `Pmoves-cipher` (no `/api/memory` routes registered in `server.ts`).
> Until the cipher-api submodule implements these routes, MCP tools will return 404.
> **Use the local fallback paths below.**

#### Fallback: local auto-memory (if CIPHER_DOWN or MCP fails)

Append the reasoning trace to your auto-memory file using the Write or Edit tool:
- File: `~/.claude/projects/<project>/memory/MEMORY.md`
- Add under a topic file (e.g., `reasoning_<topic>.md`)
- Include: question, reasoning chain, result, confidence

---

### Retrieve reasoning patterns

#### Primary: MCP tool (if CIPHER_UP)

Use the MCP tool `pmoves_cipher_reasoning_patterns`:

```
Tool: pmoves_cipher_reasoning_patterns
Arguments:
  query: "$PATTERN_QUERY"
  limit: 5
```

#### Fallback: local auto-memory (if CIPHER_DOWN or MCP fails)

Read the auto-memory files and search for reasoning-related entries using Grep:
- Search for `reasoning`, `chain-of-thought`, `Q:`, `Result:` patterns
- Check topic files with `reasoning` in the filename

---

**Notes:**
- Reasoning traces help agents learn from past decisions across sessions
- Patterns are indexed for similarity search when Cipher is fully online
- Store with descriptive questions — future searches match on semantic similarity
