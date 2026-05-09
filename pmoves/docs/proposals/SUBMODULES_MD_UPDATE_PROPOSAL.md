# Proposal: extend `.claude/context/submodules.md`

**Branch:** `docs/claude-md-modernize-fleet`
**Source:** Phase 5 of `C:\Users\russe\.claude\plans\silly-tickling-bengio.md`
**Date drafted:** 2026-05-08
**Status:** Pending approval — `.claude/context/` is read-only per `patterns.yaml:1109`. Adding the file to the allowlist (alongside lines 990, 993) and merging this delta is a separate, explicitly-approved step.

---

## Why this is gated

The damage-control hook treats `.claude/context/` as a "read-only reference" path. To accept this update, an operator must:

1. Add `.claude/context/submodules.md` to the allowlist in `.claude/hooks/damage-control/patterns.yaml` with an approval comment (cite this proposal or an issue number — the existing entries follow the pattern `# … approved per issue #1173`).
2. Apply the diff below.
3. Restore the allowlist (or leave the entry in place if ongoing edits are expected).

This intentionally adds friction so submodule registry edits remain audited.

---

## Diff to apply

Insert the following section into `.claude/context/submodules.md` between the existing `## Agent Coordination & Orchestration` block (ending around line 80) and `## MCP Tools & Extensions` (starts around line 83).

```markdown
---

## Agent Format & Skills Constellation

This tier holds the canonical reference for the **AGENTS.md open format** (universal coding-agent contract) and the **skills constellation** — POWERFULMOVES forks of upstream agent-skill repositories. Treat `PMOVES-agents.md/` as **Tier-2 always-relevant**: load it whenever discussing agent classes, taxonomy, persona schema, or AGENTS.md format itself. Skills constellation entries are **Tier-2 on-demand** — load `skills/README.md` first, then the specific skill submodule.

### PMOVES-agents.md
- **Path:** `PMOVES-agents.md/`
- **Repository:** https://github.com/POWERFULMOVES/PMOVES-agents.md
- **Upstream:** [agentsmd/agents.md](https://agents.md) — open format for guiding coding agents (Claude Code, Codex, Copilot, Cursor, etc.)
- **Purpose:** Canonical home for AGENTS.md format reference, agent taxonomy, and persona schema docs
- **Tier:** **Tier-2 always-relevant** (load when format/taxonomy/persona work touches the conversation)
- **Cross-refs:** Root `AGENTS.md` follows this format; `pmoves/docs/AGENTS/PMOVES_AGENT_CLASS_TAXONOMY.md` and `PMOVES_AGENT_TOPOLOGY.md` are taxonomy docs that may migrate here (gated on user confirmation)

### skills/ — Skills Constellation (Phase 2 forward-declaration)

Pending Phase 2 of `docs/claude-md-modernize-fleet`: five POWERFULMOVES skill forks to be added under `skills/` as nested submodules.

| Submodule | Upstream | Purpose |
|-----------|----------|---------|
| `skills/PMOVES-skills/` | [anthropics/skills](https://github.com/anthropics/skills) | Anthropic's official skills library — reference for skill authoring patterns |
| `skills/PMOVES-awesome-agent-skills/` | [heilcheng/awesome-agent-skills](https://github.com/heilcheng/awesome-agent-skills) | Curated index of skills/tools/tutorials for AI coding agents |
| `skills/PMOVES-fork-repository-skill/` | [disler/fork-repository-skill](https://github.com/disler/fork-repository-skill) | Fork the running agent N times to branch engineering work |
| `skills/PMOVES-agent-sandbox-skill/` | [disler/agent-sandbox-skill](https://github.com/disler/agent-sandbox-skill) | Manage isolated execution environments for agents |
| `skills/PMOVES-claude-d3js-skill/` | (POWERFULMOVES fork) | D3.js skill — Claude-driven data visualization patterns |

Once Phase 2 lands the submodules, this section becomes the canonical map. Until then, the forks live on the POWERFULMOVES org and can be cloned standalone.

---
```

Also update the count at the top of the file:

```diff
-**Total submodules:** 49 (including vendor/legacy dual-mounts)
+**Total submodules:** 54 (including vendor/legacy dual-mounts; +5 in `skills/` after Phase 2)
```

---

## Why this matters

- The keystone changes in this PR (root `CLAUDE.md`, `.claude/CLAUDE.md`) already point readers at `PMOVES-agents.md/` and `skills/`. Without the submodules.md entry, those pointers dangle in the canonical registry — agents who jump straight to `submodules.md` for ground truth won't find the entries.
- Surfacing `PMOVES-agents.md` as Tier-2 always-relevant in the registry (matching what the keystones now claim) prevents future drift between "what CLAUDE.md says" and "what submodules.md catalogs".
- Forward-declaring the `skills/` constellation makes Phase 2 a mechanical add (the docs already describe the target shape).

---

## After approval

1. Patch `patterns.yaml` allowlist with `- ".claude/context/submodules.md"  # approved per <issue/PR#>` near lines 990–993.
2. Apply the diff above.
3. Optionally remove the allowlist entry once the edit lands, if you don't expect repeat edits.
4. Delete this proposal file (`pmoves/docs/proposals/SUBMODULES_MD_UPDATE_PROPOSAL.md`).
