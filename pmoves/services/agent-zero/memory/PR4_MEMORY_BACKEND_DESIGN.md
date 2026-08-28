# PR #4: Cipher Memory Backend via A0 Native MCP

> **Status**: Design
> **Date**: 2026-05-09
> **Scope**: Connect Agent Zero memory plugin stubs to Cipher's memory system through A0's built-in MCP client — no custom transport code.

## 1. What This Is (and What It Is Not)

**This IS:** A0 natively supports SSE and Streamable HTTP MCP transports. Cipher exposes full memory CRUD as MCP tools in aggregator mode. We configure A0 to connect to Cipher as an MCP server, then call those tools from the memory plugin stubs through a thin circuit-breaker wrapper.

**This is NOT:**
- No `cipher_bridge.py` — there is no custom HTTP client to build
- No custom retry logic at bridge level
- No custom transport code of any kind
- A0's built-in MCP client handles ALL transport

The previous design proposed a ~250-line HTTP bridge client. This design replaces that with ~80 lines of circuit-breaker logic calling A0's existing `MCPConfig.call_tool()`.

## 2. Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Agent Zero (PMOVES fork)                                  │
│                                                             │
│  Memory Plugin Stubs (extensions/)                          │
│  ┌──────────────────┐  ┌──────────────────┐                │
│  │ _50_memorize_    │  │ _50_recall_      │                │
│  │ fragments.py     │  │ memories.py      │                │
│  └───────┬──────────┘  └───────┬──────────┘                │
│          │  (sync FAISS)        │  (FAISS first)            │
│          │                      │                            │
│          ▼                      ▼                            │
│  ┌──────────────────────────────────────┐                   │
│  │  cipher_backend.py (~80 lines)       │                   │
│  │  - Circuit breaker (3 fail → OPEN)   │                   │
│  │  - Calls MCPConfig.get_instance()    │                   │
│  │    .call_tool('cipher.TOOL', args)   │                   │
│  └──────────────┬───────────────────────┘                   │
│                 │ MCP protocol (SSE or Streamable HTTP)      │
│                 │ — A0's native MCP client                   │
└─────────────────┼───────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────┐
│  Cipher Service (MCP_MODE=aggregator)                       │
│  SSE: port 3000 | Streamable HTTP: port 3001                │
│                                                             │
│  MCP Tools exposed:                                         │
│  - cipher_memory_search                                     │
│  - cipher_extract_and_operate_memory                        │
│  - cipher_store_reasoning_memory                            │
│  - cipher_workspace_store / cipher_workspace_search         │
│  - Knowledge graph tools                                    │
└─────────────────────────────────────────────────────────────┘
```

## 3. Source Code Evidence

### 3.1 A0 MCP Handler (`/a0/helpers/mcp_handler.py`)

| Lines | Feature | Relevance |
|-------|---------|-----------|
| 31-33 | Imports `sse_client` and `streamablehttp_client` from mcp SDK | Confirms native transport support |
| 57-76 | `_determine_server_type()` | Handles: `sse`, `http-stream`, `streaming-http`, `streamable-http`, `http-streaming` |
| 223-293 | `MCPServerRemote` class | Config fields: `name`, `type`, `url`, `headers`, `init_timeout`, `tool_timeout`, `verify`, `disabled` |
| 771 | Tool naming | Convention: `{server.name}.{tool['name']}` — e.g., `cipher.cipher_memory_search` |
| 778-787 | `has_tool(tool_name)` | Requires dotted name, splits on `.` |
| 794-805 | `async def call_tool()` | Programmatic tool invocation, requires dotted name |
| 836-897 | `_execute_with_session()` | Creates MCP session per call, handles timeouts, cleanup |

### 3.2 Cipher MCP Handler (`PMOVES-BoTZ/features/cipher/pmoves_cipher/src/app/mcp/mcp_handler.ts`)

| Lines | Feature | Relevance |
|-------|---------|-----------|
| 38-43 | `initializeMcpServer()` | Accepts `mode: 'default' \| 'aggregator'` |
| 69-70 | Aggregator mode | Calls `registerAggregatedTools(server, agent, aggregatorConfig)` |
| 86-136 | Default mode | Only exposes `ask_cipher` (conversational, NOT useful for us) |
| 141-184 | Aggregator mode | Gets ALL tools via `unifiedToolManager.getAllTools()`, applies conflict resolution |
| 156-163 | Conflict resolution | `prefix` strategy adds `cipher.` prefix to conflicting tool names |
| 17-18 | Server imports | `McpSseServer` and `McpStreamableHttpServer` — SSE on port 3000, Streamable HTTP on port 3001 |

### 3.3 Memory Plugin Stubs (verified async)

| Stub | Pattern | Key Detail |
|------|---------|------------|
| `_50_memorize_fragments.py` | `async def execute()`, `async def memorize()`, `DeferredTask` for background | Calls `Memory.get()` then `db.save()` for FAISS |
| `_50_recall_memories.py` | `async def execute()`, `async def search_memories()`, `asyncio.create_task()` | Calls `db.search()` for FAISS |
| `_51_memorize_solutions.py` | Similar async pattern | Calls `db.save()` for FAISS |

All stubs already run in async context — `await MCPConfig.call_tool()` works directly. No `asyncio.run()` needed.

### 3.4 Existing Infrastructure

- `pmoves/services/agent-zero/memory/audit/` — directory exists for audit logging

## 4. Tool Name Resolution

There are two prefix layers that may combine:

1. **A0's MCP handler** (L771): prefixes with server name → `cipher.{tool_name}`
2. **Cipher's conflict resolution** (L156-163): may also add `cipher.` prefix to conflicting tools

This means the actual tool name in A0 could be:
- `cipher.cipher_memory_search` (if Cipher's conflict resolution added its own prefix)
- `cipher.memory_search` (if no conflict resolution needed)

**Resolution:** The implementation must verify actual tool names at runtime after connecting. The `cipher_backend.py` should accept tool names as configurable constants with a `cipher.` prefix, defaulting to the double-prefixed form (`cipher.cipher_*`). A startup verification call should log all available `cipher.*` tools from `MCPConfig.get_instance().get_tools()` and warn if expected names are missing.

## 5. API Flow

### 5.1 Recall (Search)

```
Agent calls memory_load tool
  → _50_recall_memories.py::execute()
    → db.search(query)  [FAISS, synchronous, always runs]
    → cipher_backend.search(query, threshold, limit)  [async, best-effort]
      → circuit breaker check (OPEN? → skip, log, return None)
      → await MCPConfig.get_instance().call_tool('cipher.cipher_memory_search', {...})
      → on success: return results for merging
      → on failure: increment fail count, log to audit/, return None
    → Merge: FAISS results (primary) + Cipher results (supplementary)
    → Return combined results to agent
```

### 5.2 Memorize (Store Fragments)

```
Agent calls memory_save tool
  → _50_memorize_fragments.py::execute()
    → db.save(text, metadata)  [FAISS, synchronous, always runs]
    → cipher_backend.store(text, metadata)  [async, fire-and-forget via DeferredTask]
      → circuit breaker check (OPEN? → skip, log)
      → await MCPConfig.get_instance().call_tool('cipher.cipher_extract_and_operate_memory', {...})
      → on success: log to audit/
      → on failure: increment fail count, log to audit/
    → Return FAISS result to agent (don't wait for Cipher)
```

### 5.3 Memorize (Store Solutions)

```
Agent calls memory_save with area='solutions'
  → _51_memorize_solutions.py::execute()
    → db.save(text, metadata)  [FAISS, synchronous, always runs]
    → cipher_backend.store_reasoning(text, metadata)  [async, fire-and-forget]
      → await MCPConfig.get_instance().call_tool('cipher.cipher_store_reasoning_memory', {...})
      → Same circuit breaker pattern
    → Return FAISS result to agent
```

## 6. Circuit Breaker Design

Reference: `CIRCUIT_BREAKER_PRINCIPLE.promptinclude.md` at project root.

### 6.1 State Machine

```
          3 consecutive failures
CLOSED ──────────────────────→ OPEN
  ↑                               │
  │         60 seconds             │
  └───────────────────────────────┘
```

No HALF-OPEN state — after 60s cooldown, go directly to CLOSED. Simplicity over sophistication. A single Cipher call succeeding proves connectivity.

### 6.2 Implementation Rules

| Rule | Implementation |
|------|---------------|
| Fail fast | Don't wait for MCP timeout if circuit is OPEN — skip immediately |
| Fail open | Return FAISS results when Cipher down, never return errors to agent |
| Fail observable | Log every state transition and failed call to `audit/` |
| Stop and reflect | Circuit breaker IS the reflection — after 3 failures, stop hitting Cipher |
| Preserve context | FAISS results are always available; Cipher is enrichment only |

### 6.3 Implementation Location

In `cipher_backend.py` only. NOT at MCP transport level. A0's MCP handler already has its own timeout/cleanup logic (L836-897). We don't modify that.

## 7. File Changes

### 7.1 New Files

| File | Lines (est.) | Purpose |
|------|-------------|---------|
| `pmoves/services/agent-zero/memory/cipher_backend.py` | ~80 | Circuit breaker + MCP call wrapper |

### 7.2 Modified Files

| File | Change | Scope |
|------|--------|-------|
| `_50_memorize_fragments.py` | Add `cipher_backend.store()` call after FAISS save (fire-and-forget) | ~10 lines added |
| `_50_recall_memories.py` | Add `cipher_backend.search()` call after FAISS search, merge results | ~15 lines added |
| `_51_memorize_solutions.py` | Add `cipher_backend.store_reasoning()` call after FAISS save (fire-and-forget) | ~10 lines added |

### 7.3 Configuration Files

| File | Change |
|------|--------|
| `.a0proj/project.json` | Add `cipher` to `mcpServers` with SSE or Streamable HTTP transport |

### 7.4 NOT Changed

| File | Reason |
|------|--------|
| `memory_load` / `memory_save` / `memory_delete` / `memory_forget` tool stubs | These call the `_50_*` / `_51_*` plugin stubs indirectly. No direct changes needed. |
| `/a0/helpers/mcp_handler.py` | No modifications — A0's MCP client handles everything |
| Any Cipher source code | No modifications — aggregator mode already exposes the tools we need |

### 7.5 NOT Created (Explicitly Rejected)

| File | Reason |
|------|--------|
| `cipher_bridge.py` | No custom HTTP client needed — A0 MCP client handles transport |
| Any custom retry/transport module | A0's `_execute_with_session()` already handles sessions, timeouts, cleanup |

## 8. `cipher_backend.py` Specification

```python
# cipher_backend.py — ~80 lines
# Location: pmoves/services/agent-zero/memory/cipher_backend.py

import logging
import time
from typing import Any, Dict, Optional
from helpers.mcp_handler import MCPConfig

logger = logging.getLogger("pmoves.cipher_backend")

# Tool names — configurable because double-prefix is uncertain
# See Section 4: Tool Name Resolution
TOOL_SEARCH = "cipher.cipher_memory_search"
TOOL_STORE = "cipher.cipher_extract_and_operate_memory"
TOOL_STORE_REASONING = "cipher.cipher_store_reasoning_memory"

# Circuit breaker constants
FAIL_THRESHOLD = 3
COOLDOWN_SECONDS = 60


class CipherBackend:
    """Thin wrapper around A0's MCP client for Cipher memory tools.

    FAISS-first: all Cipher calls are best-effort enrichment.
    Circuit breaker prevents cascading failures when Cipher is down.
    """

    def __init__(self):
        self._fail_count = 0
        self._open_until: float = 0.0

    @property
    def is_available(self) -> bool:
        """Check if circuit is closed (Cipher reachable)."""
        if self._fail_count >= FAIL_THRESHOLD:
            if time.monotonic() < self._open_until:
                return False
            # Cooldown expired — reset
            self._fail_count = 0
        return True

    def _record_failure(self):
        self._fail_count += 1
        if self._fail_count >= FAIL_THRESHOLD:
            self._open_until = time.monotonic() + COOLDOWN_SECONDS
            logger.warning(
                "Circuit OPEN — Cipher unreachable, failing back to FAISS for %ds",
                COOLDOWN_SECONDS,
            )

    def _record_success(self):
        if self._fail_count > 0:
            logger.info("Circuit closing — Cipher call succeeded")
        self._fail_count = 0

    async def call(self, tool_name: str, args: Dict[str, Any]) -> Optional[Any]:
        """Call a Cipher MCP tool with circuit breaker protection.

        Returns None on any failure (circuit open, MCP error, timeout).
        Never raises — callers always get a result or None.
        """
        if not self.is_available:
            return None

        try:
            mcp = MCPConfig.get_instance()
            result = await mcp.call_tool(tool_name, args)
            self._record_success()
            return result
        except Exception as e:
            logger.warning("Cipher MCP call failed: %s", e)
            self._record_failure()
            # Audit log
            _audit_log("cipher_call_failed", tool_name=tool_name, error=str(e))
            return None

    async def search(self, query: str, threshold: float = 0.3,
                     limit: int = 5) -> Optional[Any]:
        return await self.call(TOOL_SEARCH, {
            "query": query,
            "threshold": threshold,
            "limit": limit,
        })

    async def store(self, text: str, metadata: Dict[str, Any]) -> Optional[Any]:
        return await self.call(TOOL_STORE, {
            "text": text,
            **metadata,
        })

    async def store_reasoning(self, text: str, metadata: Dict[str, Any]) -> Optional[Any]:
        return await self.call(TOOL_STORE_REASONING, {
            "text": text,
            **metadata,
        })


# Module-level singleton
_backend: Optional[CipherBackend] = None


def get_backend() -> CipherBackend:
    global _backend
    if _backend is None:
        _backend = CipherBackend()
    return _backend


def _audit_log(event: str, **kwargs):
    """Write to audit log. Implementation deferred to audit/ module."""
    try:
        # Import lazily to avoid circular deps
        from pmoves.services.agent_zero.memory.audit import log_event
        log_event(event, **kwargs)
    except ImportError:
        logger.debug("Audit module not available, skipping log: %s", event)
```

## 9. Plugin Stub Modifications

### 9.1 `_50_recall_memories.py` — Search Enrichment

Add after FAISS `db.search()` call, before returning results:

```python
# After FAISS search results are obtained
from pmoves.services.agent_zero.memory.cipher_backend import get_backend

cipher_results = await get_backend().search(query, threshold=threshold, limit=limit)
if cipher_results is not None:
    # Merge: append Cipher results as supplementary entries
    # FAISS results are primary, Cipher results are enrichment
    # Deduplicate by text similarity if needed (future optimization)
    merged = list(faiss_results)  # copy
    merged.extend(_parse_cipher_results(cipher_results))
    return merged
return faiss_results  # Cipher unavailable, FAISS-only
```

The `_parse_cipher_results()` helper extracts text/content from Cipher's MCP response format into the same shape as FAISS results so downstream code doesn't need to know the source.

### 9.2 `_50_memorize_fragments.py` — Fire-and-Forget Store

Add after FAISS `db.save()` call:

```python
# Fire-and-forget Cipher mirror — don't await, don't block return
from pmoves.services.agent_zero.memory.cipher_backend import get_backend

def _cipher_mirror(text, metadata):
    import asyncio
    asyncio.create_task(get_backend().store(text, metadata))

DeferredTask(_cipher_mirror, text=text, metadata=metadata)
```

Uses the existing `DeferredTask` pattern already present in the stub for background execution. FAISS save completes synchronously, Cipher mirror runs in background.

### 9.3 `_51_memorize_solutions.py` — Fire-and-Forget Reasoning Store

Same pattern as 9.2 but calls `store_reasoning()`:

```python
from pmoves.services.agent_zero.memory.cipher_backend import get_backend

def _cipher_reasoning_mirror(text, metadata):
    import asyncio
    asyncio.create_task(get_backend().store_reasoning(text, metadata))

DeferredTask(_cipher_reasoning_mirror, text=text, metadata=metadata)
```

## 10. project.json MCP Server Configuration

Add to `.a0proj/project.json` under `mcpServers`:

```json
{
  "mcpServers": {
    "cipher": {
      "name": "cipher",
      "type": "streamable-http",
      "url": "http://cipher-host:3001/mcp",
      "headers": {},
      "init_timeout": 10,
      "tool_timeout": 30,
      "verify": true,
      "disabled": false
    }
  }
}
```

**Transport choice:** Streamable HTTP (port 3001) preferred over SSE (port 3000) — it's the newer MCP transport with better session management. If Cipher doesn't expose Streamable HTTP in the deployed version, fall back to `"type": "sse"` with `"url": "http://cipher-host:3000/sse"`.

**URL resolution:** In production, `cipher-host` is resolved via Tailscale DNS. In local dev, use `host.docker.internal` or the Cipher container name from docker-compose.

**Authentication:** If Cipher requires auth, add to `headers`: `{"Authorization": "Bearer <token>"}`. Token sourced from environment, not hardcoded.

## 11. Embedding Model Mismatch

**Problem:** A0 uses OpenAI embeddings for FAISS. Cipher uses its own embedder (configured in Cipher's brain settings). The same query will produce different embeddings, so FAISS results and Cipher results may differ for identical queries.

**Impact:** Low. This design treats Cipher as enrichment, not replacement. Different embeddings mean Cipher may return relevant results that FAISS missed (complementary recall) or may return results FAISS already found (duplicate recall).

**Mitigation in this PR:** Accept the mismatch. Document it. Deduplicate merged results by text similarity in `_parse_cipher_results()` if needed.

**Future optimization (not this PR):** Align embedding models between A0 and Cipher, or use Cipher's embedder for FAISS as well.

## 12. Migration Path

### Step 1: Cipher Aggregator Mode (Prerequisite)

Ensure Cipher service runs with `MCP_MODE=aggregator`:

```bash
# In Cipher's environment/docker-compose
MCP_MODE=aggregator
```

Verify tools are exposed:

```bash
curl -s http://cipher-host:3001/mcp | jq '.tools[].name'
# Expected: cipher_memory_search, cipher_extract_and_operate_memory, ...
```

### Step 2: Add MCP Server Config

Add the `cipher` entry to `.a0proj/project.json` `mcpServers` (see Section 10).

### Step 3: Deploy cipher_backend.py

Place at `pmoves/services/agent-zero/memory/cipher_backend.py`.

### Step 4: Modify Plugin Stubs

Add Cipher calls to `_50_memorize_fragments.py`, `_50_recall_memories.py`, `_51_memorize_solutions.py` per Section 9.

### Step 5: Verify Tool Names

Start A0, check logs for available `cipher.*` tools. Verify the actual dotted names match the constants in `cipher_backend.py`. Adjust if double-prefix doesn't occur.

### Step 6: Test

Run the test plan (Section 14). FAISS should work identically to before. Cipher calls should appear in audit logs.

### Rollback

If anything breaks: remove the Cipher `mcpServers` entry from project.json. Plugin stub modifications are no-ops when Cipher backend returns `None` (circuit opens immediately). No code rollback needed — just config.

## 13. What Gets Deleted (from Wrong Previous Design)

| Artifact | Status |
|----------|--------|
| `cipher_bridge.py` | **DO NOT CREATE** — not needed |
| Custom HTTP client | **DO NOT CREATE** — A0 MCP client handles transport |
| Custom retry logic at bridge level | **DO NOT CREATE** — circuit breaker in cipher_backend.py is sufficient |

## 14. Testing Strategy

### 14.1 Unit Tests

| Test | Description |
|------|-------------|
| `test_circuit_breaker_opens` | 3 failures -> `is_available` returns False |
| `test_circuit_breaker_cooldown` | After 60s, `is_available` returns True |
| `test_circuit_breaker_resets_on_success` | Success after 2 failures resets counter |
| `test_call_returns_none_on_open` | `call()` returns None when circuit is open |
| `test_call_returns_none_on_exception` | `call()` returns None on MCP exception, doesn't raise |
| `test_call_returns_result_on_success` | `call()` returns MCP result on success |

### 14.2 Integration Tests

| Test | Description |
|------|-------------|
| `test_cipher_mcp_tools_available` | Verify `cipher.*` tools appear in MCPConfig after connection |
| `test_recall_returns_faiss_when_cipher_down` | Stop Cipher, run recall -> get FAISS results only, no errors |
| `test_recall_merges_cipher_results` | Cipher up, run recall -> results include both FAISS and Cipher entries |
| `test_memorize_faiss_succeeds_when_cipher_down` | Stop Cipher, run memorize -> FAISS save succeeds, no errors |
| `test_audit_log_written_on_failure` | Force Cipher failure -> audit log entry exists in `audit/` |

### 14.3 Manual Verification

1. Start A0 with Cipher MCP configured and Cipher running
2. Call `memory_save` -> verify FAISS save + audit log shows Cipher store
3. Call `memory_load` -> verify results include Cipher-enriched entries
4. Stop Cipher -> call `memory_load` -> verify FAISS-only results, circuit opens in log
5. Wait 60s -> restart Cipher -> call `memory_load` -> verify circuit closes, Cipher results return

## 15. Observability

### 15.1 Audit Log Events

Written to `pmoves/services/agent-zero/memory/audit/`:

| Event | Fields | When |
|-------|--------|------|
| `cipher_call_failed` | `tool_name`, `error` | Every Cipher MCP call failure |
| `cipher_circuit_open` | `fail_count` | Circuit transitions to OPEN |
| `cipher_circuit_close` | — | Circuit resets to CLOSED |

### 15.2 Logging

| Level | Message | When |
|-------|---------|------|
| WARNING | `Circuit OPEN — Cipher unreachable...` | Circuit opens |
| INFO | `Circuit closing — Cipher call succeeded` | Circuit resets |
| WARNING | `Cipher MCP call failed: {error}` | Individual call failure |
| DEBUG | `Audit module not available...` | Audit module missing (non-critical) |

## 16. Security Considerations

- **No secrets in cipher_backend.py** — MCP connection config is in project.json, auth tokens in environment
- **No data exposure** — Cipher calls contain the same data already in FAISS (agent memories)
- **Tailscale transport** — In production, MCP traffic flows over Tailscale VPN, not public internet
- **No new attack surface** — We're using A0's existing MCP client, not adding new network code

## 17. Open Questions

| # | Question | Resolution |
|---|----------|------------|
| 1 | Does Cipher's conflict resolution actually add `cipher.` prefix? | Verify at runtime after Step 5. Default to double-prefixed names. |
| 2 | What is Cipher's MCP response format for search results? | Inspect `CallToolResult` content after first successful call. `_parse_cipher_results()` adapts. |
| 3 | Should `cipher_workspace_store`/`cipher_workspace_search` be used? | Not in initial scope. Add in follow-up PR if workspace persistence is needed. |
| 4 | Rate limiting on Cipher MCP calls? | A0's `tool_timeout` (30s) provides per-call bounding. No explicit rate limiting needed for enrichment calls. |

## 18. Summary

This PR adds Cipher as an MCP server to A0's project config, then calls Cipher's memory tools from the existing plugin stubs through an ~80-line circuit-breaker wrapper. FAISS remains the primary memory store. Cipher is enrichment only. If Cipher is unreachable, the circuit breaker opens and everything degrades gracefully to FAISS-only with zero impact to the agent.

Total new code: ~80 lines (cipher_backend.py) + ~35 lines (stub modifications) = **~115 lines**.
Total deleted code: **0 lines** (purely additive, fully backward compatible).
