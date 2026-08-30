# PMOVES.AI Living Documents Index

**One page. All current docs. No jumping.** This is the navigable surface for the docs that actually move — keystones, fleet state, taxonomy, runbooks. Hidden registry data lives at `pmoves/configs/living_docs_registry.yaml`; this file is the human-readable face of it.

> Tracked freshness, severity, and budgets are gated by `make -C pmoves docs-reconcile-check`. Any doc out of budget surfaces in CI before drift becomes invisible.

---

## Tier 0 — Always loaded

| Doc | Path | Role | Freshness budget |
|-----|------|------|------------------|
| Root keystone | [`CLAUDE.md`](./CLAUDE.md) | Thin pointer to every other tier | 30d / P2 |
| Universal coding-agent contract | [`AGENTS.md`](./AGENTS.md) | Project structure, build/test, security | 30d / P2 |
| Flat foundation | [`.claude/BOOTSTRAP.md`](./.claude/BOOTSTRAP.md) | Emperor-CHIT-Humility, Known Roads, MCP entrypoints | 30d / P1 |

## Tier 1 — High-velocity living docs

| Doc | Path | Role | Freshness budget |
|-----|------|------|------------------|
| Service catalog | [`.claude/context/services-catalog.md`](./.claude/context/services-catalog.md) | Ports, URLs, health endpoints — drifts fastest | **14d / P1** |
| Active claim register | [`pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md`](./pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md) | Who's working on what right now (Village Rule) | **3d / P1** |
| Cold-start sitrep | [`pmoves/docs/AGENTS/AGNOTE4482_SITREP.md`](./pmoves/docs/AGENTS/AGNOTE4482_SITREP.md) | Current convergence state for fresh sessions | **7d / P1** |
| Multi-agent gateway | [`pmoves/docs/AGENTS/AGNOTE4482.md`](./pmoves/docs/AGENTS/AGNOTE4482.md) | Three-Body, signoff gate, audit trail | 14d / P1 |

## Tier 2 — Reference patterns (stable, periodic)

| Doc | Path | Role | Freshness budget |
|-----|------|------|------------------|
| Known Roads + dev patterns | [`.claude/PATTERNS.md`](./.claude/PATTERNS.md) | CHIT, skill pairings, hook recovery, debug recipes | 30d / P2 |
| Pinokio launcher guide | [`.claude/PINOKIO_LAUNCHER_GUIDE.md`](./.claude/PINOKIO_LAUNCHER_GUIDE.md) | On-demand for `D:\pinokio\` work | 60d / INFO |

## Tier 3 — Architecture thesis (slow-changing)

| Doc | Path | Role |
|-----|------|------|
| MOF architecture | [`pmoves/docs/architecture/PMOVES_MOF_ARCHITECTURE.md`](./pmoves/docs/architecture/PMOVES_MOF_ARCHITECTURE.md) | Metal-Organic Framework thesis (PR #1378) |
| Grand Convergence | [`pmoves/docs/architecture/PMOVES_GRAND_CONVERGENCE.md`](./pmoves/docs/architecture/PMOVES_GRAND_CONVERGENCE.md) | Five-layer unification (PR #1379) |
| Room manifest contract | [`pmoves/docs/ROOM_MANIFEST_CONTRACT.md`](./pmoves/docs/ROOM_MANIFEST_CONTRACT.md) | Rooms-on-a-stage interface |

---

## UI surfaces — where docs become interactive

These are the rendering targets. Doc updates should propagate visually through these, not stop at markdown.

| Surface | Repo / module | Doc anchor |
|---------|---------------|------------|
| **A2UI** (NATS-backed agent UI bridge) | [`PMOVES-A2UI/`](./PMOVES-A2UI/) | `.claude/context/geometry-nats-subjects.md` (`a2ui.*` subjects) |
| **Hyperdimensions** (visualization layer) | [`Pmoves-hyperdimensions/`](./Pmoves-hyperdimensions/) | submodule README + skill `/hyperdim:*` |
| **D3JS skill** (Claude-driven viz) | [`skills/Pmoves-claude-d3js-skill/`](./skills/Pmoves-claude-d3js-skill/) | [`skills/README.md`](./skills/README.md) |
| **Creator pipeline — image/render farm** (ComfyUI fork; no Remotion here) | `PMOVES-Creator/` | [`pmoves/docs/CREATOR_PIPELINE.md`](./pmoves/docs/CREATOR_PIPELINE.md) |
| **Creator pipeline — motion/Remotion runtime** (A2UI Renderer, port 8107: `A2UIComposition`, `ProvenanceLivingDoc`) | [`pmoves/services/a2ui-renderer/`](./pmoves/services/a2ui-renderer/) | [`pmoves/docs/CREATOR_PIPELINE.md`](./pmoves/docs/CREATOR_PIPELINE.md) |
| **Pretext text layout** (deterministic wrap/caption/living-doc overlays in the Remotion runtime) | npm `@chenglou/pretext@0.0.6` via `pmoves/services/a2ui-renderer/src/remotion/pretextLayout.ts`; [`Pmoves-pretext` fork](https://github.com/POWERFULMOVES/Pmoves-pretext) wired as submodule `Pmoves-pretext/` (#2227) | [`pmoves/docs/CREATOR_PIPELINE.md`](./pmoves/docs/CREATOR_PIPELINE.md) §text_layout |
| **PreTeXt math authoring — a DIFFERENT "pretext"** (pretextbook.org structured-document language; not the layout engine above) | [`pmoves/rooms/persona/pretext/`](./pmoves/rooms/persona/pretext/) — buildable project (`pretext build web`, pretext-cli 2.45.0): *CHIT & the MOF: A Structural Isomorphism* | persona living-doc room lane (#2236–#2247); room manifest [`persona.room.livingdoc.json`](./pmoves/config/rooms/persona.room.livingdoc.json) |
| **Three-Body Doctrine** (foundational: Human/AI/System as a three-body problem stabilized by CHIT geometry — root of the Village Rule + register Three-Body Pattern) | [`pmoves/docs/PMOVESCHIT/THREE_BODY_DOCTRINE.md`](./pmoves/docs/PMOVESCHIT/THREE_BODY_DOCTRINE.md) | referenced by AGNOTE4482 Canonical Pointers; was orphaned from discovery surfaces until 2026-08-09 |
| **CHIT Visual Tour — web dashboard** (public explainer, armor tokens; evidence policy: verified actuals only, projections labeled) | [`website/chit-tour/`](./website/chit-tour/) | content source-of-truth = `data.js` SOURCES map; sibling code-first walkthrough: [`pmoves/docs/PMOVESCHIT/VISUAL_TOUR.md`](./pmoves/docs/PMOVESCHIT/VISUAL_TOUR.md) — keep the two cross-linked, they drift independently |
| **Skills — two distinct registries** | (1) submodule↔skills↔context map: [`pmoves/configs/submodule_skill_registry.json`](./pmoves/configs/submodule_skill_registry.json) (machine-emitted; commands in [`.claude/commands/`](./.claude/commands/)); (2) operator-workflow skills (bringup-audit, secrets-chit-funnel, submodule-parity, persona-grounding, multimodal-verifier) | [`pmoves/docs/AGENTS/PmovesSKillZ.md`](./pmoves/docs/AGENTS/PmovesSKillZ.md) — not the same thing as the `skills/` 5-fork constellation below |
| **A2UI NATS bridge** (port 9224) | service-side | `.claude/CATALOG.md` |

## CLI surfaces — operator-facing entry points

The doc fleet should be reachable from the CLI without operators having to know paths.

| CLI surface | Skill / command | Doc anchor |
|-------------|-----------------|------------|
| Voice agents in CLI | `/voice:status`, `/voice:synthesize`, `/tts:*`, `/pipecat:*` | [`.claude/context/flute-gateway.md`](./.claude/context/flute-gateway.md) |
| System health check | `/health:quick`, `/health:check-all`, `/health:metrics` | [`.claude/CATALOG.md`](./.claude/CATALOG.md) |
| Bring-up validation audit | `/deploy:preflight`, `/deploy:audit-layers`, `/deploy:smoke-test` | [`pmoves/docs/operations/`](./pmoves/docs/operations/) |
| Living-docs reconciler | `make -C pmoves docs-reconcile-check` | [`pmoves/configs/living_docs_registry.yaml`](./pmoves/configs/living_docs_registry.yaml) |
| Theme & creator pipeline | `/hyperdim:*`, `/yt:*`, `/jellyfin:*` | per-skill output |
| Fleet view | `/fleet:status`, `make -C pmoves fleet-status` | [`.claude/context/runner-topology.md`](./.claude/context/runner-topology.md) |

---

## Submodule constellation — where domain context lives

| Tier | Submodule | Role |
|------|-----------|------|
| Tier-2 always-relevant | [`PMOVES-agents.md/`](./PMOVES-agents.md/) | AGENTS.md format reference + agent taxonomy |
| Tier-2 on-demand | [`skills/`](./skills/) — see [`skills/README.md`](./skills/README.md) | 5-skill constellation (Anthropic skills, agent-sandbox, fork-repository, awesome-agent-skills, claude-d3js) |
| Tier-2 on-demand | [`PMOVES-Agent-Zero/`](./PMOVES-Agent-Zero/) | Orchestration / MCP API |
| Tier-2 on-demand | [`PMOVES-Archon/`](./PMOVES-Archon/) | Agent service architecture |
| Tier-2 on-demand | [`PMOVES-HiRAG/`](./PMOVES-HiRAG/) | Hi-RAG v2 retrieval gateway |
| Full registry | [`.claude/context/submodules.md`](./.claude/context/submodules.md) | All 52 documented submodules cataloged |

---

## Archived docs

> The following submodule audit docs are superseded by the AGNOTE4482 convergence record and have been moved to `pmoves/docs/archive/`.

| Original path | Archived to | Status |
|---------------|-------------|--------|
| `docs/submodules-upstream-audit.md` | `pmoves/docs/archive/submodules-upstream-audit-2026-01-29.md` | → archived |
| `docs/submodules-audit-final-summary.md` | `pmoves/docs/archive/submodules-audit-final-summary-2026-02-17.md` | → archived |
| `pmoves/docs/AGENTS/AGNOTE_P7_PLAYGROUND.md` | `pmoves/docs/archive/AGNOTE_P7_PLAYGROUND-2026-04-10.md` | → archived |

**Note:** All submodule audit findings have been consolidated into [`AGNOTE4482.md`](./pmoves/docs/AGENTS/AGNOTE4482.md) as of the May 9 convergence entry. The individual audit docs above are retained for historical reference only.

## Planned

| Doc | Expected path | Role |
|-----|---------------|------|
| DARKXSIDE standalone architecture | `pmoves/docs/architecture/DARKXSIDE_STANDALONE_ARCHITECTURE.md` | Hostinger-deployed DarkXSide isolation topology |

---

## Adding a doc to this index

1. Add it to [`pmoves/configs/living_docs_registry.yaml`](./pmoves/configs/living_docs_registry.yaml) with a freshness budget + severity.
2. Add a row to the appropriate tier table above.
3. Verify with `make -C pmoves docs-reconcile-check` — registry-driven, no code change required.

The registry is the source of truth; this index is the navigable face. Don't drift them.

---

## Active fleet state (rolling)

Operator-visible state that the doc fleet should reflect, captured as of this index update:

- **Knuckles** — node coming online (verify in [`fleet:status`](./.claude/context/runner-topology.md))
- **Kilocode** — ClaWZ active (Discord agent runtime, replaces legacy BoTZ Gateway)
- **Spark** — pending: run `nemoclaws` (claim via AGNOTE4482PHI.t1)

This block is intentionally short. Long-form fleet state belongs in `pmoves/docs/AGENTS/AGNOTE4482_SITREP.md`.
