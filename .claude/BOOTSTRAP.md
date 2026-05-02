# PMOVES.AI Bootstrap

**Flat foundation. Load this always. Load deeper context only when your task needs it.**

You are on a PMOVES.AI node (Z890 / 5090 / 4090 / KVM4-1 / KVM4-2 / KVM2 / Jetson / SPARK / Cloudflare Edge). Per PR #1378 MOF Architecture: **every node is a pore in the lattice — capacity-class, not expertise-lane.** Run PMOVES to your physical capacity. Delegate across nodes via the paths below when a task exceeds your local reach.

## Emperor-CHIT-Humility — disclose at session start

Before editing or non-trivial work, state which you have vs missing:

- [ ] **Cipher MCP** reachable (`http://localhost:8105/health`)
- [ ] **A2A** reachable (`GET /.well-known/agent-card.json` on Agent Zero)
- [ ] **Known Roads** loaded (table below)
- [ ] **CHIT passphrase** set (`$CHIT_PASSPHRASE`; unsigned fallback is acceptable in dev)
- [ ] **Node-peer visibility** (`make -C pmoves fleet-status`)
- [ ] **MCP/service catalog** loaded (see CATALOG.md when needed)

Missing items are not failures — they are operational facts. Disclose them. Never bluff awareness.

## Known Roads — dangerous ops route through Make targets

| Need | Known Road |
|------|------------|
| Start / restart services | `make -C pmoves up-<service>` (never `docker compose up` raw) |
| Apply secrets | `make -C pmoves secrets-funnel` (before any service start after env change) |
| Read-only health | `make -C pmoves health-quick` / `health-check-all` |
| Fleet view | `make -C pmoves fleet-status` (never raw `tailscale status` for public IPs) |
| CHIT-sign provenance | `make -C pmoves sign-trail SUMMARY=... AGENT=...` |
| Refresh living docs | `make -C pmoves docs-reconcile` |

Full Known Roads catalog lives in `.claude/PATTERNS.md § Known Roads`. When the damage-control hook converts a raw `docker` / `netsh` / `gh workflow run` command to an `ask` prompt, that means a Make target already exists — use it.

## MCP Entrypoints (configured in `.claude/mcp.json`)

| Server | Transport | Purpose |
|--------|-----------|---------|
| `pmoves-cipher` | SSE `http://localhost:8105/sse` | Persistent agent memory lookups + writes |
| `docker` | `mcp/docker` | Container inspection via local Docker socket |
| `hostinger-mcp` | stdio | Hostinger VPS API via `HOSTINGER_API_KEY` |
| `tailscale` | stdio | Tailnet inventory, stale-node cleanup, ACL operations |

## Cross-node delegation — three paths

| Path | When to use |
|------|-------------|
| **Agent Zero MCP** `POST http://localhost:8080/mcp/command` | Orchestration, task delegation, subordinate agent spawn |
| **A2A** `GET /.well-known/agent-card.json` (plumbing wired via PR #1293; activate via `A0_SET_a2a_server_enabled=true`) | Peer discovery, task submission across nodes |
| **NATS** `agent.peer.heartbeat.v1` (Phase D, pending mutual-watching skill) | Continuous peripheral observation of peer nodes |

No task requires all three — pick the narrowest path that delivers. When A2A is disabled (default), say so in your disclosure; don't pretend cross-node delegation is available.

## Where to look next

| You want | Load |
|----------|------|
| Service ports, URLs, health endpoints | [`CATALOG.md`](./CATALOG.md) |
| Full Known Roads, dev patterns, CHIT, skill pairings | [`PATTERNS.md`](./PATTERNS.md) |
| Who's working on what right now | `pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md` § Active Claim Register |
| Cold-start orientation | `pmoves/docs/AGENTS/AGNOTE4482_SITREP.md` |
| Gateway pointers (audits, waves, Three-Body) | `pmoves/docs/AGENTS/AGNOTE4482.md` |
| Architecture-level thesis | `pmoves/docs/architecture/PMOVES_MOF_ARCHITECTURE.md` + `PMOVES_GRAND_CONVERGENCE.md` |
| Submodule-specific context | That submodule's `CLAUDE.md` — opt-in only, not auto-loaded |

## Rules that survive every session

1. **Leverage existing services, don't rebuild.** Hi-RAG v2 for retrieval, NATS for events, MinIO via Presign for artifacts, Agent Zero `/mcp/*` for orchestration. The catalog exists.
2. **Test before PR.** `/test:pr` + document the Testing section. Docstring coverage ≥80% on new Python.
3. **Never raw docker / tailscale CLI** for operations with Make-target equivalents. The hooks will block and redirect.
4. **Village Rule.** No agent operates alone in production validation. Claim (AGNOTE4482PHI.t1), work, sign, release.
5. **Signing is optional locally, never skipped for session-end provenance.** `sign-trail` emits unsigned if `CHIT_PASSPHRASE` unset — that's fine in dev, still run it.
6. **Prefer the minimum task scope.** If you find adjacent cleanups, open a follow-up; don't expand the current claim.

## When context feels heavy

If this file is all you remember, you can still do the right thing:
- Ask "is there a Make target for this?" — if yes, use it.
- Ask "is this file in `CATALOG.md` or `PATTERNS.md`?" — if yes, load it.
- Ask "have I disclosed what I don't know?" — if no, do that first.

The rest is scaffolding.
