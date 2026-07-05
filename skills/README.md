# PMOVES.AI Skills Constellation

POWERFULMOVES forks of upstream agent-skill repositories. Each entry is a git submodule under `skills/` that tracks an upstream skill library, lets us layer PMOVES-specific changes, and stays discoverable as a single constellation.

## Tier

**Tier 2 — On-Demand (Major Subsystem).** Load this README first. Load a specific skill submodule's CLAUDE.md / README only when working in that skill's domain.

## Constellation

| Submodule | Path | Upstream | Purpose | Status |
|-----------|------|----------|---------|--------|
| `Pmoves-skills` | `skills/Pmoves-skills/` | [anthropics/skills](https://github.com/anthropics/skills) | Anthropic's official skills library — reference for skill authoring patterns | ✅ Added |
| `PMOVES-awesome-agent-skills` | `skills/PMOVES-awesome-agent-skills/` | [heilcheng/awesome-agent-skills](https://github.com/heilcheng/awesome-agent-skills) | Curated index of skills/tools/tutorials for AI coding agents | ✅ Added (2026-05-09) |
| `pmoves-fork-repository-skill` | `skills/pmoves-fork-repository-skill/` | [disler/fork-repository-skill](https://github.com/disler/fork-repository-skill) | Fork the running agent N times to branch engineering work | ✅ Activated (2026-05-15) — pointer at `.claude/skills/fork-repository/` |
| `PMOVES-agent-sandbox-skill` | `skills/PMOVES-agent-sandbox-skill/` | [disler/agent-sandbox-skill](https://github.com/disler/agent-sandbox-skill) | Manage isolated execution environments for agents | ✅ Activated (2026-05-15) — pointer at `.claude/skills/agent-sandbox/` |
| `Pmoves-claude-d3js-skill` | `skills/Pmoves-claude-d3js-skill/` | [chrisvoncsefalvay/claude-d3js-skill](https://github.com/chrisvoncsefalvay/claude-d3js-skill) | D3.js skill — Claude-driven data visualization | ✅ Activated (2026-05-15) — pointer at `.claude/skills/claude-d3js/` |

## Adding more skill forks (future)

All five entries in the constellation table landed across two singleton rounds on 2026-05-09 (z890). Adding new external skill forks crosses an untrusted-code-integration boundary that requires both:

1. A damage-control allowlist entry if any read-only path is touched (see `.claude/hooks/damage-control/patterns.yaml`).
2. **Per-URL Bash-tool authorization** — the runtime gates each external repo URL separately, even after general approval. The cleanest path is for an operator to run the singleton add as a `! <command>` in a Claude Code prompt, or directly in a shell.

The `.claude/context/submodules.md` registry is the canonical map of these forks; `pmoves/configs/submodule_skill_registry.json` carries context-tag injection rules.

## Activation paths

How each skill becomes available to a Claude Code session:

- **`Pmoves-skills/`** — clone of Anthropic's skill repo. Most relevant skills are already published as plugins (e.g., `superpowers:*`); this fork is a reference for *authoring* new skills.
- **`PMOVES-awesome-agent-skills/`** — read as documentation; entries link out to upstream skill repos.
- **`pmoves-fork-repository-skill/`** — registers as a Claude Code skill; activate via the skill registry once added to `.claude/skills/` or imported as a plugin.
- **`PMOVES-agent-sandbox-skill/`** — same activation path as fork-repository-skill.
- **`Pmoves-claude-d3js-skill/`** — Claude Code skill for D3.js visualization; activate via the skill registry.

## Cross-references

- Root `CLAUDE.md` — keystone, points here as Tier-2 constellation
- `.claude/CLAUDE.md` — context loading priority (Tier 2 entry references this README)
- `.claude/context/submodules.md` — comprehensive submodule registry (pending the proposal in `pmoves/docs/proposals/`)
- `PMOVES-agents.md/` — sibling Tier-2 always-relevant submodule for AGENTS.md format reference
- `pmoves/configs/submodule_skill_registry.json` — context-tag injection registry; new skill submodules should be registered here once they have CLAUDE.md files
