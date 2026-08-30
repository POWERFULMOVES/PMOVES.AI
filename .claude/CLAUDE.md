# PMOVES.AI Developer Context

**Always-on context for Claude Code CLI (and any coding agent) working in the PMOVES.AI repository.**

> **Read [`BOOTSTRAP.md`](./BOOTSTRAP.md) first. It's the flat foundation (≤5k chars).** This file is scaffolding around that.

## Architecture Overview

PMOVES.AI is a production-ready multi-agent orchestration platform: autonomous agent coordination via Agent Zero; hybrid RAG (Hi-RAG v2) combining vector + graph + full-text search; multimodal holographic deep research (SupaSerch); comprehensive observability (Prometheus, Grafana, Loki); event-driven architecture via NATS; media processing pipeline (YouTube, Whisper, YOLO).

Per PR #1378 MOF Architecture: PMOVES is a Metal-Organic Framework for distributed machine intelligence — **every node is a pore in the lattice**. Capacity-class, not expertise-lane. Per PR #1379 Grand Convergence: five layers (L1 Structure → L5 Economics) unify MOF, CHIT, GEOMETRY_BUS, EVO SWARM, ToKenism as one system.

## Where to find what

| You want | Load |
|----------|------|
| Flat foundation (always) | [`BOOTSTRAP.md`](./BOOTSTRAP.md) |
| Service ports, URLs, health endpoints | [`CATALOG.md`](./CATALOG.md) |
| Known Roads, credentials, CHIT, skill pairings, hook recovery, dev patterns | [`PATTERNS.md`](./PATTERNS.md) |
| Who's working on what right now | `pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md` § Active Claim Register |
| Cold-start orientation | `pmoves/docs/AGENTS/AGNOTE4482_SITREP.md` |
| Audit gateway + convergence waves | `pmoves/docs/AGENTS/AGNOTE4482.md` |
| Architecture thesis | `pmoves/docs/architecture/PMOVES_MOF_ARCHITECTURE.md`, `PMOVES_GRAND_CONVERGENCE.md` |
| Agent taxonomy & autonomy model | [`pmoves/config/agent_registry.yaml`](../pmoves/config/agent_registry.yaml) — the source of truth (`classes`, `types`, `role_classes`, `resilience_classes`, every agent). Prose hub: [`AGENT_TAXONOMY_CROSS_REFERENCE.md`](../pmoves/docs/AGENTS/AGENT_TAXONOMY_CROSS_REFERENCE.md) |
| AGENTS.md *format* convention | [`PMOVES-agents.md/`](../PMOVES-agents.md/) — fork of agentsmd/agents.md. It is the upstream **website** (61 blobs, all Next.js) and its own `AGENTS.md` documents how to run that site. It carries **no** PMOVES taxonomy or persona content — verified at the pinned commit, 2026-08-30 |
| Skills constellation | [`skills/`](../skills/) — Anthropic skills, agent-sandbox, fork-repository, awesome-agent-skills, claude-d3js (see `skills/README.md`) |
| Pinokio launcher development | [`PINOKIO_LAUNCHER_GUIDE.md`](./PINOKIO_LAUNCHER_GUIDE.md) — on-demand context for `D:\pinokio\` work |
| Living-docs freshness rules | [`pmoves/configs/living_docs_registry.yaml`](../pmoves/configs/living_docs_registry.yaml) — tracked by `make -C pmoves docs-reconcile-check` |
| Per-subsystem detail | that subsystem's `CLAUDE.md` — opt-in only (Tier 2/3 below) |

## Context Loading Priority (For ALL Agents)

**Tier 1 — Always Load (Critical System Context):**
- `.claude/BOOTSTRAP.md` (flat, ≤5k chars)
- `.claude/CLAUDE.md` (this file)
- `pmoves/docs/AGENTS/AGNOTE4482_SITREP.md` (cold-start orientation)

**Tier 2 — On-Demand (Major Subsystems):**
- `PMOVES-agents.md/` — the agents.md **website** fork, nothing more. This line
  used to promise "agent taxonomy/persona docs"; a recursive listing of the
  pinned tree finds zero files matching taxonomy / persona / pmoves / capacity /
  autonomy. The submodule is also unpopulated locally, so anyone following the
  old pointer found nothing and moved on rather than discovering the gap.
  The taxonomy lives in `pmoves/config/agent_registry.yaml` +
  `pmoves/docs/AGENTS/`. The agents.md convention specifies one thing — a
  root `AGENTS.md` in plain Markdown for coding agents — and has no vocabulary
  for class, persona, or autonomy, so there is no upstream model to map onto.
- `PMOVES-Archon/.claude/CLAUDE.md` — agent service architecture
- `PMOVES-BoTZ/.claude/CLAUDE.md` — skills marketplace framework (legacy/archived per 2026-04-19)
- Agent Zero — the submodule has **no** `.claude/CLAUDE.md` (verified 2026-08-06). Use `pmoves/services/agent-zero/README.md` for the service, and `pmoves/docs/operations/AGENT_ZERO_API.md` for the live API surface.
- `skills/` — skills constellation. **5 forks in `.gitmodules`**: `PMOVES-skills` (the package/CLI, tracking `PMOVES.AI-Edition-Hardened`), agent-sandbox, fork-repository, awesome-agent-skills, claude-d3js. The skill *sources* — Anthropic's `Pmoves-Claude-skills` and MiniMax's `Pmoves-Minimax-skills` — are nested under `PMOVES-skills/sources/`, so populate with `git submodule update --init --recursive skills/`; load `skills/README.md` first
- Load only when working directly on that subsystem.

**Tier 3 — Conditional (Integration Workspaces):**
- `integrations-workspace/*/CLAUDE.md` — cross-submodule integration points
- Load only for integration tasks.

**Tier 4 — Explicit Only (Nested Contexts):**
- Submodule nested submodules (e.g., `PMOVES-Archon/external/*/`)
- Individual skill contexts (e.g., `PMOVES-BoTZ/features/skills/*/CLAUDE.md`)
- Load only when explicitly requested.

## Additional References

Detail files live in `.claude/context/`:
- `runner-topology.md` — condensed node/runner/team topology
- `credentials-workflow.md` — credential bootstrap, secrets-funnel, JWT-from-Supabase
- `services-catalog.md` — full service listing (superset of CATALOG.md)
- `submodules.md` — submodules catalog (52 documented rows; `.gitmodules` tracks 72 — see the header of that file for why the three counts differ)
- `nats-subjects.md` — comprehensive NATS subject catalog
- `geometry-nats-subjects.md` — GEOMETRY BUS NATS subjects (`tokenism.*`, `geometry.*`)
- ~~`mcp-api.md`~~ — **SUPERSEDED, do not use as an API reference.** It documents `/mcp/command`, `/mcp/health`, `/mcp/task/{id}`, `/mcp/agents`, `/mcp/subordinate/create`, `/mcp/subordinate/create-with-persona` and an `MCP_CLIENT_SECRET` Bearer scheme that were never implemented. Canonical: `pmoves/docs/operations/AGENT_ZERO_API.md`.
- `testing-strategy.md` — testing workflow + PR requirements
- `security-patterns.md` — cross-cutting security patterns (auth, secrets, hardening)
- `observability-patterns.md` — Prometheus, Grafana, Loki, TensorZero metrics
- ~~`agent-zero-orchestration.md`~~ — **SUPERSEDED, do not use as an API reference.** It documents `/mcp/health`, `/mcp/agents`, `/mcp/subordinate/create` and an `agent.zero.*` NATS family that were never implemented. Canonical: `pmoves/docs/operations/AGENT_ZERO_API.md` (probed from `/openapi.json`).
- `tier-architecture.md` — 7-tier env security model, network segmentation
- `chrome-extension.md` — Chrome Extension integration (8 services, message protocol, auth)
- `tensorzero.md` — TensorZero detailed documentation
- `flute-gateway.md` — Flute-Gateway API reference

**CHIT-Aware Services:** Tokenism Simulator (8103), Hi-RAG v2 (8086/8087), Gateway, Consciousness (8106), Evo Controller (8113), A2UI NATS Bridge (9224), AgentGym RL Coordinator. See `pmoves/docs/audit/CHIT_INTEGRATION_STATUS.md` for per-service status (5 Full, 8 Partial, 15 None).

## Git Worktree Workflow

**Why worktrees?** Isolated development branches without cloning entire repo. Required for rebase work on shared branches. Prevents polluting the main working tree with in-progress changes.

| Operation | Command |
|-----------|---------|
| List all worktrees | `git worktree list` (or `/worktree:list`) |
| Create new | `git worktree add ../pmoves-<name> <branch>` (or `/worktree:create`) |
| Create w/ new branch | `git worktree add -b <new-branch> ../pmoves-<name> <base>` |
| Switch | `cd ../pmoves-<name>` (or `/worktree:switch`) |
| Clean up stale | `git worktree prune` (or `/worktree:cleanup`) |
| Remove named | `git worktree remove --force <path>` (Windows file locks can leave residue — next `prune` clears) |

When working in a worktree, Claude Code loads context from that worktree's location. Be aware of which branch you're on.

**Authoritative worktree sitrep:** `make -C pmoves worktree-sitrep-strict` (non-zero exit on any dirty/conflicted worktree). Prefer this to per-worktree spot checks.

## Agent Context Pattern (Universal)

For Claude Code CLI and all PMOVES.AI agents:

1. **Check current location first.** Verify which repo / worktree / node you're in. Disclose it.
2. **Load appropriate context tier.** Don't auto-load all submodule contexts.
3. **Respect context boundaries.** Nested submodule contexts are opt-in, not default.
4. **Use service APIs, don't rebuild.** Leverage existing production services (see CATALOG.md).
5. **Check service health before use.** Verify `/healthz` endpoints.
6. **Publish events to NATS** for cross-component coordination.

## Context Conflict Resolution

**Precedence hierarchy:**
1. Main repo context > submodule contexts
2. Higher-level contexts > nested contexts
3. Recent contexts > legacy contexts

When conflicts occur: main PMOVES.AI patterns take precedence; document exceptions in submodule-specific CLAUDE.md; use NATS for cross-module coordination, not duplicated logic.

## Avoiding Context Loops

**Problem:** nested submodules can create circular context loading (Archon → BoTZ → skills → back to Archon patterns).

**Solution:**
- Each agent loads only its direct tier
- Use MCP APIs for cross-agent communication, not shared context
- Reference integration docs instead of duplicating (note: `pmoves/docs/integrations/ARCHON_INTEGRATION.md` is **superseded** — it describes the pre-0.6.0 Python/Supabase Archon; current state is `.claude/CATALOG.md` + `pmoves/docs/handoffs/ARCHON_MINT_CONTRACT_REVIEW.md`)

Full audit: `pmoves/docs/CLAUDE_CONTEXT_AUDIT.md`.

## MCP Integration Points

**Agent Zero supervisor REST API** on port 8080 — `GET /healthz`, `GET /mcp/commands`, `POST /mcp/execute` (`{cmd, arguments}`), `POST /tasks`, `GET /jobs/{context_id}`, `POST /sessions`, `/memory/*`, `POST /events/publish`. **No inbound auth** on these routes. It is a REST facade, not an MCP protocol server; there is no `/mcp/*` wildcard mount.

**Agent Zero MCP protocol server** — served by the A0 runtime on port 8081 at `/t-{MCP_SERVER_TOKEN}/sse`, `/t-{...}/http`, `/t-{...}/messages/`. The runtime authenticates with `X-API-KEY`. A2A routes (`/a2a/v1/*`, `/.well-known/agent-card.json`) on 8080 use a Supabase JWT `Authorization: Bearer`, gated by `A2A_DISCOVERY_PUBLIC` / `A2A_TASKS_PUBLIC`.

**Configured local MCP servers** (`.claude/mcp.json`):
- `pmoves-cipher` (SSE `http://localhost:8105/mcp/sse`) — persistent memory lookups + writes. Path verified 2026-08-12 against the running container; `/sse` and `/api/mcp/sse` both 404.
- `docker` (`mcp/docker`) — container inspection via local Docker socket
- `hostinger-mcp` — Hostinger API tasks via `$HOSTINGER_API_KEY`
- `tailscale` — tailnet inventory, stale-node cleanup, tag inspection, ACL operations

**Enabled operator plugin pack** (`.claude/settings.json`): `huggingface-skills@claude-plugins-official` — use when Hub models, datasets, Spaces, or launch recipes are the source of truth.

**Configuration:** set `AGENTZERO_JETSTREAM=true` for reliable delivery. For Agent Zero, set `AGENT_ZERO_MCP_TOKEN` (the A0 runtime's inbound `X-API-KEY` / MCP path token) and `AGENT_ZERO_API_KEY` (what the supervisor forwards to the runtime). `MCP_SERVICE_URL`, `MCP_CLIENT_ID` and `MCP_CLIENT_SECRET` are **not read by any PMOVES service** — they appear nowhere under `pmoves/services/`. You will still see `MCP_CLIENT_SECRET` in tier env files because `pmoves/tools/brand_defaults.py:405-410` auto-generates one; it has no consumer. Do not send it as an auth header.

## Meta-Instruction for Claude Code CLI

When developing features for PMOVES.AI:

1. **Leverage existing services** — don't rebuild what exists (see CATALOG.md).
2. **Use NATS for coordination** — event-driven communication (see PATTERNS.md § NATS).
3. **Expose health/metrics** — follow observability patterns.
4. **Check health first** — always verify service status before use.
5. **Consult context docs** — reference `.claude/context/` for details.
6. **Test before PR** — run `/test:pr` and document results (see PATTERNS.md § Testing).
7. **Respect context tiers** — load only appropriate context level for your task.
8. **Disclose gaps** — emperor-CHIT-humility at session start (see BOOTSTRAP.md).

PMOVES.AI is a sophisticated production system. Your role is to build features that integrate with this ecosystem, not replace it.

## Determining User Intent (from URLs and brief prompts)

If the initial prompt is simply a URL and nothing else, check the website content and determine intent, then ask the user to confirm. URLs may point to:

1. **Tutorial** — intent may be to implement a demo + build a launcher
2. **Demo** — intent may be a 1-click launcher for the demo
3. **Open source project** — intent may be a 1-click launcher for the project
4. **Regular website** — intent may be to clone the website + launcher

Always confirm with the user before committing to an interpretation.

## Development Principles

1. **Minimize Shell Usage** — leverage API parameters over raw commands.
2. **Maintain Separation** — keep app logic and launchers separate (Pinokio projects).
3. **Follow Conventions** — match existing project patterns.
4. **Test Thoroughly** — use CLI + Make targets to verify.
5. **Document Changes** — update relevant metadata + documentation.

## Quick Reference Summary

| Need | Load |
|------|------|
| What am I on / what do I know / what's missing | `BOOTSTRAP.md` (disclosure + Known Roads + delegation paths) |
| Service address, port, health endpoint | `CATALOG.md` |
| Known Road, CHIT rule, skill pairing, debug recipe | `PATTERNS.md` |
| Active claims / Village Rule coordination | `pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md` |
| Cold-start orientation | `pmoves/docs/AGENTS/AGNOTE4482_SITREP.md` |
| Architecture thesis | `PMOVES_MOF_ARCHITECTURE.md`, `PMOVES_GRAND_CONVERGENCE.md` |

**End state:** you should be able to do 90% of routine PMOVES work with just `BOOTSTRAP.md` loaded. Reach for `CATALOG.md`/`PATTERNS.md` when a task demands them. Load a submodule's `CLAUDE.md` only when editing that submodule.
