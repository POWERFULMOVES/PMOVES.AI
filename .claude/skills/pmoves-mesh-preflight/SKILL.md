---
name: pmoves-mesh-preflight
description: Run /healthz across every service in .claude/CATALOG.md and emit pass/fail. Use before claiming work in AGNOTE4482PHI.t1.md.
---

# pmoves-mesh-preflight

Runs a catalog-driven health snapshot across all PMOVES.AI services declared in `.claude/CATALOG.md`. Emit pass/fail before opening a CLAIM entry in `pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md` so the worker can disclose the mesh state at session start (Emperor-CHIT-Humility).

## When to use

- Before claiming a lane in the Active Claim Register
- Before merging any PR that touches a service in `.claude/CATALOG.md`
- As part of `/test:pr` smoke flow
- When a recipe in `.claude/PATTERNS.md` recommends a preflight gate

## How to invoke

```bash
bash .claude/skills/pmoves-mesh-preflight/scripts/preflight.sh
```

The script:

1. Parses port + endpoint hints from `.claude/CATALOG.md`.
2. Issues `curl -sS --max-time 3 http://127.0.0.1:<port>/healthz` (falls back to `/health` for known exceptions like Cipher Memory).
3. Prints a fixed-width table: `service | port | status | latency_ms`.
4. Exits non-zero (1) if **any** service responds with HTTP >= 400 or times out.

## Output

```
service                 | port | status | latency_ms
------------------------+------+--------+-----------
agent-zero              | 8080 | 200    | 12
archon                  | 8091 | 200    | 9
cipher-memory           | 8105 | 200    | 7
flute-gateway           | 8055 | 503    | 3
...
FAIL: 1 service(s) unhealthy
```

## Citations

- `.claude/CATALOG.md` — authoritative port catalog
- `pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md` — Active Claim Register (record preflight result alongside CLAIM)
- `.claude/PATTERNS.md` § Known Roads — companion recipe
