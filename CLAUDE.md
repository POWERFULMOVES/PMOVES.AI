# PMOVES.AI — Root Context

PMOVES.AI is a **Metal-Organic Framework (MOF)** for distributed machine intelligence — the crystalline lattice through which autonomous agents flow. Operationally, this manifests as a **rooms-on-a-stage** model with **P7 (Pinokio 7)** as the room-aware stage manager (selects rooms, loads suits, manages stage transitions: rehearsal → live → review → archive).

This file is a thin keystone. Always-loaded context lives in `.claude/BOOTSTRAP.md`; project structure lives in `AGENTS.md`; multi-agent coordination lives in `pmoves/docs/AGENTS/AGNOTE4482.md`. Don't dump content here — extend the right downstream file.

## Read first (always)

1. **[`LIVING_DOCS_INDEX.md`](LIVING_DOCS_INDEX.md)** — front-and-center map of every living doc + UI/CLI surface (no jumping)
2. **[`.claude/BOOTSTRAP.md`](.claude/BOOTSTRAP.md)** — flat foundation: Emperor-CHIT-Humility, Known Roads, MCP entrypoints, cross-node delegation paths
3. **[`AGENTS.md`](AGENTS.md)** — project structure, build/test commands, canonical documentation index (universal coding-agent format)
4. **[`pmoves/docs/AGENTS/AGNOTE4482_SITREP.md`](pmoves/docs/AGENTS/AGNOTE4482_SITREP.md)** — cold-start sitrep, current convergence state

## Tiered context map

| You want | Load |
|----------|------|
| Service catalog (ports, URLs, health endpoints) | [`.claude/CATALOG.md`](.claude/CATALOG.md) |
| Known Roads, CHIT, skill pairings, hook recovery, dev patterns | [`.claude/PATTERNS.md`](.claude/PATTERNS.md) |
| Multi-agent coordination gateway (Three-Body, Village Rule, signoff) | [`pmoves/docs/AGENTS/AGNOTE4482.md`](pmoves/docs/AGENTS/AGNOTE4482.md) |
| Active claims register | [`pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md`](pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md) |
| Architecture thesis | [`pmoves/docs/architecture/PMOVES_MOF_ARCHITECTURE.md`](pmoves/docs/architecture/PMOVES_MOF_ARCHITECTURE.md), [`PMOVES_GRAND_CONVERGENCE.md`](pmoves/docs/architecture/PMOVES_GRAND_CONVERGENCE.md) |
| AGENTS.md format reference & agent taxonomy | [`PMOVES-agents.md/`](PMOVES-agents.md/) submodule (fork of agentsmd/agents.md) |
| Skills constellation (Anthropic skills, agent-sandbox, fork-repository, awesome-agent-skills, claude-d3js) | [`skills/`](skills/) submodules + `skills/README.md` |
| Submodule-specific patterns | that submodule's `CLAUDE.md` — opt-in only, not auto-loaded |
| Living-docs freshness rules | [`pmoves/configs/living_docs_registry.yaml`](pmoves/configs/living_docs_registry.yaml) |

## Rooms-on-a-stage

P7 is the runtime launcher and fleet orchestrator — not just a process spawner, but the room-aware stage manager. It knows which rooms exist (via `pmoves/config/rooms/catalog.json`), selects the appropriate room profile for a workload, and manages the lifecycle (rehearsal → live → review → archive). NATS subjects `p7.nats.launch` and `p7.nats.session` are the control plane.

- [`pmoves/docs/ROOM_MANIFEST_CONTRACT.md`](pmoves/docs/ROOM_MANIFEST_CONTRACT.md) — room interface specification
- [`pmoves/config/rooms/catalog.json`](pmoves/config/rooms/catalog.json) — room registry

## Pinokio launcher development

This repo also serves as the home for Pinokio launcher scripts that pair with `D:\pinokio\`. The full Pinokio API guide, execution checklist, and `start.js` URL-capture pattern moved to **[`.claude/PINOKIO_LAUNCHER_GUIDE.md`](.claude/PINOKIO_LAUNCHER_GUIDE.md)** — load it on demand when writing or modifying launcher scripts. Source-of-truth API docs remain `D:\pinokio\prototype\PINOKIO.md`.

## End state

You should be able to do 90% of routine PMOVES work with `BOOTSTRAP.md` + `AGENTS.md` loaded. Reach for `CATALOG.md` / `PATTERNS.md` when a task demands them. Load a submodule's `CLAUDE.md` only when editing that submodule. Load `PINOKIO_LAUNCHER_GUIDE.md` only when touching launcher scripts.

When in doubt: disclose what you have vs what's missing (Emperor-CHIT-Humility, see BOOTSTRAP.md).
