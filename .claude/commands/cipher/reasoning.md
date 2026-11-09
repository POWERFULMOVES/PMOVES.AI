# Cipher Reasoning

Store and retrieve reasoning traces and patterns in Cipher Memory.

## Instructions

Manage reasoning traces in Cipher Memory. Use MCP tools as the primary path.
If Cipher is unreachable or MCP fails, fall back to local auto-memory.
Do NOT let a connection failure interrupt your workflow.

### Step 1: Health check (silent, non-blocking)

```bash
curl -sf --max-time 3 http://localhost:8105/health > /dev/null 2>&1 && echo "CIPHER_UP" || echo "CIPHER_DOWN"
```

---

### Store a reasoning trace

#### Primary: MCP tool (if CIPHER_UP)

Use the MCP tool `pmoves_cipher_store_reasoning`:

```yaml
Tool: pmoves_cipher_store_reasoning
Arguments:
  question: "$QUESTION"
  reasoning: "$CHAIN_OF_THOUGHT"
  result: "$FINAL_ANSWER"
  metadata: { "task": "$TASK", "confidence": 0.85 }
```

> **RETRACTED 2026-09-09 — this blocker was measurably false.** It read: "MCP tools
> are currently blocked ... `GET /api/memory/search` ... does not exist in
> `Pmoves-cipher` (no `/api/memory` routes registered in `server.ts`) ... Use the
> fallback below." That instruction told every agent to SKIP cipher, and agents
> followed it.
>
> Measured on Z890 against the live container at submodule pin `e24f1323`:
> `POST /api/memory` -> **201** with a non-null `embedding_id`, and a semantic
> recall phrased differently from the stored text returned the new record. The
> routes exist — `Pmoves-cipher/src/pmoves/memory-routes.ts`. The A1-Shim
> re-implemented them (`Pmoves-cipher/PMOVES.AI_INTEGRATION.md` §Contracts), which
> is exactly what the 2026-04-01 note was waiting for; nobody came back to clear it.
>
> **The blocker you WILL hit instead is identity, not routing.** Every store/search
> call requires `agentId`, and it must match the agent your token was minted for:
>
> ```
> 403 token belongs to agent 'bootstrap', but request specified 'z890-claude'
> ```
>
> A node holding a shared `bootstrap` token refuses your real signing-card id
> (`pmoves/config/signing_identity_cards.yaml`). That is the credential being
> mis-provisioned, not the service being down — do not "fix" it by falling back.
> Cross-agent `agentId: "*"` is refused outright under token enforcement
> (`memory-routes.ts`). Remedy is a per-agent mint through the CHIT pipeline.
>
> **Never** read `CIPHER_API_TOKEN` out of `docker inspect` or a container env to
> work around this. That is a CHIT-pipeline bypass; it was done during this
> investigation and it was wrong. If the MCP server is not connected in your
> session, say so and use auto-memory — that is the documented rule, not a
> failure state.

#### Fallback: local auto-memory (if CIPHER_DOWN or MCP fails)

Append the reasoning trace to your auto-memory file using the Write or Edit tool:
- File: `~/.claude/projects/<project>/memory/MEMORY.md`
- Add under a topic file (e.g., `reasoning_<topic>.md`)
- Include: question, reasoning chain, result, confidence

---

### Retrieve reasoning patterns

#### Primary: MCP tool (if CIPHER_UP)

Use the MCP tool `pmoves_cipher_reasoning_patterns`:

```yaml
Tool: pmoves_cipher_reasoning_patterns
Arguments:
  query: "$PATTERN_QUERY"
  limit: 5
```

#### Fallback: local auto-memory (if CIPHER_DOWN or MCP fails)

Read the auto-memory files and search for reasoning-related entries using Grep:
- Search for `reasoning`, `reasoning_trace`, `chain-of-thought`, `Q:`, `Result:` patterns
- Check topic files with `reasoning` in the filename
- **Legacy note:** Historical entries may use category `reasoning_trace` instead of `reasoning`.
  Search for both when retrieving patterns from older sessions.

---

**Notes:**
- Reasoning traces help agents learn from past decisions across sessions
- Patterns are indexed for similarity search when Cipher is fully online
- Store with descriptive questions — future searches match on semantic similarity
