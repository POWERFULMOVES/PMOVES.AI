# PMOVES.AI Skills Constellation

POWERFULMOVES forks of upstream agent-skill repositories. Each entry is a git submodule under `skills/` that tracks an upstream skill library, lets us layer PMOVES-specific changes, and stays discoverable as a single constellation.

## Tier

**Tier 2 — On-Demand (Major Subsystem).** Load this README first. Load a specific skill submodule's CLAUDE.md / README only when working in that skill's domain.

## Constellation

| Submodule | Path | Upstream | Purpose | Status |
|-----------|------|----------|---------|--------|
| `Pmoves-skills` | `skills/Pmoves-skills/` | [anthropics/skills](https://github.com/anthropics/skills) | Anthropic's official skills library — reference for skill authoring patterns | ✅ Added |
| `PMOVES-awesome-agent-skills` | `skills/PMOVES-awesome-agent-skills/` | [heilcheng/awesome-agent-skills](https://github.com/heilcheng/awesome-agent-skills) | Curated index of skills/tools/tutorials for AI coding agents | ⏳ Pending operator approval |
| `pmoves-fork-repository-skill` | `skills/pmoves-fork-repository-skill/` | [disler/fork-repository-skill](https://github.com/disler/fork-repository-skill) | Fork the running agent N times to branch engineering work | ⏳ Pending operator approval |
| `PMOVES-agent-sandbox-skill` | `skills/PMOVES-agent-sandbox-skill/` | [disler/agent-sandbox-skill](https://github.com/disler/agent-sandbox-skill) | Manage isolated execution environments for agents | ⏳ Pending operator approval |
| `Pmoves-claude-d3js-skill` | `skills/Pmoves-claude-d3js-skill/` | [chrisvoncsefalvay/claude-d3js-skill](https://github.com/chrisvoncsefalvay/claude-d3js-skill) | D3.js skill — Claude-driven data visualization | ⏳ Pending operator approval |

## Why "pending operator approval"

Adding external submodules from forks crosses a security boundary: untrusted-code integration. The damage-control hook flagged batch additions as scope-escalation. To complete the constellation, an operator with `Bash(git submodule add:*)` permission needs to run:

```bash
git submodule add https://github.com/POWERFULMOVES/PMOVES-awesome-agent-skills.git skills/PMOVES-awesome-agent-skills
git submodule add https://github.com/POWERFULMOVES/pmoves-fork-repository-skill.git skills/pmoves-fork-repository-skill
git submodule add https://github.com/POWERFULMOVES/PMOVES-agent-sandbox-skill.git skills/PMOVES-agent-sandbox-skill
git submodule add https://github.com/POWERFULMOVES/Pmoves-claude-d3js-skill.git skills/Pmoves-claude-d3js-skill
```

After running, update the Status column above to ✅ and update `.claude/context/submodules.md` per the proposal in `pmoves/docs/proposals/SUBMODULES_MD_UPDATE_PROPOSAL.md`.

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
