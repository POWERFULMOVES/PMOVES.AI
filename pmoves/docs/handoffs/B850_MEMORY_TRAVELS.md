# B850 memory travels — handoff

Lane: `feat/b850-memory-travels` (B850-CLAUDE / Knuckles, claim filed 2026-10-08T12:26:29Z).

Goal: a B850-CLAUDE session (and Z890/5090/4090/SPARK siblings) boots on ANY
node with its memory reachable.

## Gaps (measured 2026-10-08)

| # | Gap | Status |
|---|-----|--------|
| 1 | Fleet roster entry `pmoves-cipher` (tailnet Z890 :8105/mcp/sse) answers 401; `pmoves-cipher-local` (localhost:8105) works | investigating |
| 2 | `brv` (ByteRover CLI, `byterover-cli`) absent on knuckles; launcher says nothing | investigating |
| 3 | cipher `agent_checkpoint` rows record `harness:"unknown"`, `model:"unknown"` | investigating |

Findings are appended per gap below as each is resolved.
