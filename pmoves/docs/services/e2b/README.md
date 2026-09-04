# E2B — Agentic Computer Use Services

**Status:** Submodule-pointer tier (no in-tree compose deployment — 2026-09-03 full-fleet audit)

---

## Overview

E2B provides **self-hosted isolated sandboxes** for AI-generated code execution using Firecracker microVMs: untrusted code runs in disposable microVMs, never on fleet nodes. The PMOVES integration lives as **five Hardened submodules + one in-tree MCP bridge service**, not as an in-tree compose stack.

### Actual layout (audit-verified 2026-09-03)

| Component | Location | Status |
|-----------|----------|--------|
| `PMOVES-E2B-Danger-Room` | repo-root submodule (Hardened, e2b-dev/E2B fork) | source fork; synced via merge-upstream 2026-09-03 |
| `PMOVES-E2B-Danger-Room-Desktop` | repo-root submodule | NoVNC desktop client fork |
| `PMOVES-E2b-Spells` | repo-root submodule | code-execution patterns |
| `PMOVES-Remote-View` | repo-root submodule | web UI (surf) |
| `pmoves-e2b-mcp-server` | repo-root submodule | MCP bridge |
| `pmoves/services/agent-zero` | in-tree | A0 consumes the MCP bridge when configured |

**There are no `e2b-*` services in any `pmoves/docker-compose*.yml` and no `e2b-*` make targets.** Any doc section describing compose entries, ports (7073/3080/6080/7070), or vendor paths under `pmoves/pmoves/vendor/e2b-*` describes a deployment that does not exist in-tree.

## Bringing it up (real paths)

1. **Self-hosting infra** — Terraform in the upstream pattern: `e2b-dev/infra` (AWS/GCP). The fork carries SDK + templates; infra deployment is a dedicated lane, not a compose command.
2. **Sandbox SDK access** — `E2B_API_KEY` via the secrets funnel (dashboard.e2b.dev when using hosted E2B instead of self-host).
3. **Agent Zero integration** — the `pmoves-e2b-mcp-server` bridge submodule; register as an MCP server in the A0 config (see `pmoves/config/mcp_inventory.json` patterns).

## Fleet context

- Skill: `pmoves-e2b-danger-room` (Hermes profile) — SDK usage, self-host path, sibling map
- Danger-Room pattern: untrusted agent code → firewapped microVMs → never on fleet nodes
- Related docs: `pmoves/docs/integrations/E2B_INTEGRATION.md`, `.claude/context/nats-subjects.md`

## Reintegration options (tracked)

The 2026-09-03 audit ranked e2b the #1 reintegration candidate by fleet-value × drift. Two paths:
- **(a)** Land real `e2b-*` compose entries + make targets matching this README's service table (runtime work), or
- **(b)** Keep submodule-pointer status (this rewrite) and delete the phantom deployment sections — chosen for now; path (a) remains open as a lane.
