# LEARNINGS — 6-repo fold-in PR2 (model cascade: MiniMax-MCP + minimax-cli + MiniMax-Provider-Verifier)

> Per the 4-bucket taxonomy (missed-signal / fix-pattern / wrong-suggestion / already-addressed).
> Captured during implementation, before any review. Add more buckets as review threads land.

## 1. The slice as a whole

**Goal:** fold 3 upstream forks into PMOVES.AI as top-level submodules. Operator chose **3 separate PRs** for revert granularity (PR1=skills, PR2=model-cascade, PR3=agents.md). This file covers **PR2 (model cascade)**.

**3 stacked commits on `feat/mcpcli-foldin` (off `d4af79f325` = main @ 2026-08-17, post-PR1-merge):**

| # | SHA | What |
|---|-----|------|
| 1 | `33c5ae608a` | feat(submodule): fold in 3 forks — `.gitmodules` + 3 new gitlinks (MCP, CLI, Provider-Verifier) |
| 2 | `9a63212829` | docs(context): register 3 submodules in `.claude/context/submodules.md` + `pmoves/configs/submodule_skill_registry.json` |
| 3 | (pending) | docs(agnote): AGNOTE CLAIM row + this LEARNINGS file |

**Acceptance criteria status:**

| # | Criterion | Status |
|---|-----------|--------|
| 1 | `PMOVES-MiniMax-MCP/` exists as a gitlink at upstream HEAD | Done (commit 1, `f4d6a61b`) |
| 2 | `Pmoves-minimax-cli/` exists as a gitlink at upstream HEAD | Done (commit 1, `24875e0f`) |
| 3 | `Pmoves-MiniMax-Provider-Verifier/` exists as a gitlink at upstream HEAD | Done (commit 1, `53d2d8a0`) |
| 4 | `.gitmodules` has 3 new entries (all tracking `branch = main`) | Done (commit 1) |
| 5 | `submodules.md` has 3 new H3 sections in their semantic sections (MCP → "MCP Tools & Extensions"; CLI + Provider-Verifier → "Development Tools") | Done (commit 2) |
| 6 | `submodule_skill_registry.json` has 3 new entries (MCP tier=2, CLI+Provider-Verifier tier=3) | Done (commit 2) |
| 7 | AGNOTE CLAIM row appended | Done (commit 3) |
| 8 | JSON parses | Verified with `python -c "import json; json.load(...)"` |
| 9 | 3-PR strategy preserved (3 submodules in 1 PR, not 1 per PR) | Per operator choice |

**Out of scope (intentional, lives in other PRs of the fold-in):**

- `PMOVES-skills` — PR1, MERGED at `d4af79f325` / #2586.
- `PMOVES-agents.md` — PR3.
- The deprecated pre-recenter URL `Pmoves-Minimax-skills` — preserved as a README reference in PR1.

## 2. Patterns / fixes

### 2.1 "Why these 3 are one PR, not 3" — the tier argument

**The trap:** with 3 forks in this PR, the natural reflex is to ask "should each be its own PR?" That would be over-engineering.

**The decision:** keep the 3 forks in 1 PR because they form a single tier (the model surface). The MCP server is useless without a CLI to call it from the sidecar lane, and useless without a verifier to gate new providers against. The 3-PR strategy already gives the operator 3 layers of revert granularity (skills / model-cascade / agents.md format); splitting each PR further would mean a partial model cascade, which is worse than no model cascade.

**Rule of thumb:** a PR is a logical tier, not a logical repo. If splitting the PRs would leave a tier partially complete, don't split. The granularity lives in the choice of tiers, not the choice of repos within a tier.

### 2.2 The 3 submodules go at the repo root, not under `skills/`

**The convention:** the 5 entries in the skills constellation are at `skills/<fork-name>/` (nested). New top-level forks (PMOVES-Agent-Zero, PMOVES-Archon, PMOVES-BoTZ, etc.) go at the repo root.

**Why:** the skills constellation is a discoverable group (with its own README + recenter note). The 3 forks in PR2 are tier-2 context loaders (MCP, CLI, verifier) that don't share a constellation README; they sit alongside the other first-tier forks. The submodules.md table groups them by semantic section (MCP Tools & Extensions, Development Tools).

**Rule of thumb:** if the new submodule has a constellation README + activation path, put it under `skills/`. Otherwise, it goes at the repo root in its semantic section.

### 2.3 Submodule branch = `main` for fresh forks, `PMOVES.AI-Edition-Hardened` for hardened fleet

**The convention:** most PMOVES.AI submodules track `PMOVES.AI-Edition-Hardened` (the fork's PMOVES-overlay branch). The exceptions (skills/*, tooling, independent-release-cadence forks) track `main`.

**For PR2:** all 3 forks are fresh fold-ins, no PMOVES overlay yet. They track `main` (the upstream default). When/if PMOVES-specific changes need to land, a `PMOVES.AI-Edition-Hardened` branch is created on the fork and the gitlink is bumped — same pattern as the Slice 2 forks (PMOVES-hermes-agent, PMOVES-pinokio) which were branch-bumped post-merge in the branch protection refactor (PR #2490).

**Rule of thumb:** fresh forks track `main` until they need a PMOVES overlay. When they need one, create the branch in the fork and bump the gitlink.

### 2.4 The `domain_tags` reflect the role, not the tech

**For PMOVES-MiniMax-MCP:** `["mcp", "agents", "llm"]` — the role is "MCP server for agents consuming LLMs".
**For Pmoves-minimax-cli:** `["llm", "agents"]` — the role is "CLI for agents consuming LLMs" (no MCP tag because it's a CLI, not an MCP server).
**For Pmoves-MiniMax-Provider-Verifier:** `["llm", "infra", "ci"]` — the role is "CI gate for new LLM providers".

**Rule of thumb:** the `domain_tags` array is consumed by the skill-tag injector to decide what context to load. Tag by what the consumer cares about, not by what technology the submodule uses. The MCP server is "mcp" because consumers look for it under the MCP tag; the CLI is not "mcp" because consumers look for it under the CLI tag (and there's no `cli` tag yet, so it gets the closest match: `llm, agents`).

## 3. Wrong-suggestion / Already-addressed (none this slice)

No review threads yet — this is a pre-review LEARNINGS capture. If codex/CodeRabbit surfaces findings, they'll be appended to the 4-bucket taxonomy below.

## 4. Cross-refs

- `AGNOTE4482PHI.t1.md` row `Mavis::MCPCLI-FOLDIN::2026-08-17` — the CLAIM
- `AGNOTE4482PHI.t1.md` row `Mavis::SKILLS-FOLDIN::2026-08-17` — PR1, MERGED
- `.claude/context/submodules.md` — the registry table (3 new H3 sections)
- `pmoves/configs/submodule_skill_registry.json` — the context-tag injector map (3 new entries)
- PR1 (MERGED) and PR3 (pending) — the other 2 PRs of the fold-in
