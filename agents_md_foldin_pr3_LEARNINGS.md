# LEARNINGS - 6-repo fold-in PR3 (agents.md fold-in: PMOVES-agents.md)


> **CORRECTION (2026-08-20).** The "recentering" premise below is wrong. `MiniMax-AI/skills` never moved to `vercel-labs/skills` — both are alive, share no history, and are different kinds of thing (a 17-skill MIT *collection* vs the "npx skills" *tool*). `Pmoves-Minimax-skills` is therefore NOT deprecated; it is a live source, now tracked at `PMOVES-skills/sources/`. Kept as written otherwise, since this records what was believed at the time. See `skills/README.md` § Correction.

> Per the 4-bucket taxonomy (missed-signal / fix-pattern / wrong-suggestion / already-addressed).
> Captured during implementation, before any review. Add more buckets as review threads land.

## 1. The slice as a whole

**Goal:** fold 6 upstream forks into PMOVES.AI as proper submodules, one slice per "logical group". Operator chose **3 separate PRs** for revert granularity (PR1=skills, PR2=MCP+CLI+Provider-Verifier, PR3=agents.md). This file covers **PR3 (agents.md fold-in)**.

**3 stacked commits on `feat/agents-md-foldin` (off `d4af79f325` = main @ post-PR1-merge, 2026-08-17):**

| # | SHA | What |
|---|-----|------|
| 1 | `56df840207` | feat(submodule): fold in PMOVES-agents.md - `.gitmodules` new entry (with `branch = main` added manually, since `git submodule add` without `-b` doesn't set it) + new `PMOVES-agents.md/` gitlink at upstream HEAD `d1ac7f063d20e70015ed6732664049ae4ba9d74e` |
| 2 | `224a727559` | docs(context): register PMOVES-agents.md in `.claude/context/submodules.md` (one-row table under the existing `### PMOVES-agents.md` subsection, mirroring the `skills/*` table format below) + `pmoves/configs/submodule_skill_registry.json` (new `PMOVES-agents.md` entry, context_tier=2, domain_tags=["agents","docs"]) |
| 3 | (this commit) | docs(agnote): AGNOTE CLAIM row + this LEARNINGS file |

**Acceptance criteria status:**

| # | Criterion | Status |
|---|-----------|--------|
| 1 | `PMOVES-agents.md/` exists as a gitlink at the upstream HEAD | Done (commit 1) |
| 2 | `.gitmodules` has the entry (url=POWERFULMOVES/PMOVES-agents.md, branch=main) | Done (commit 1) |
| 3 | `.claude/context/submodules.md` has a sibling table row (mirroring `skills/*` table format) | Done (commit 2) |
| 4 | `pmoves/configs/submodule_skill_registry.json` has the new entry (context_tier=2, domain_tags=["agents","docs"]) | Done (commit 2) |
| 5 | AGNOTE CLAIM row appended | Done (commit 3) |
| 6 | JSON parses | Verified with `python -c "import json; json.load(...)"` (58 submodules, +1) |
| 7 | 3-PR strategy adopted (not 1 mega-PR or 6 micro-PRs) | Per operator choice (3 separate PRs for revert granularity) |
| 8 | LEARNINGS file at worktree root (`agents_md_foldin_pr3_LEARNINGS.md`, not `mcpcli_*` which is for PR2) | Done (commit 3) |

**Out of scope (intentional, lives in other PRs of the fold-in):**

- `PMOVES-skills` (`skills/PMOVES-skills`) - already MERGED as PR1 (#2586).
- The 3 MCP+CLI+Provider-Verifier repos - PR2.

## 2. Patterns / fixes

### 2.1 `git submodule add` without `-b` doesn't set the `branch` field in `.gitmodules`

**The trap:** the operator spec was `.gitmodules`: new entry with `branch = main`. `git submodule add URL PATH` (no `-b`) does NOT set `branch` in the .gitmodules entry - it only sets the gitlink to the default branch HEAD. The entry it writes looks like:

```ini
[submodule "PMOVES-agents.md"]
	path = PMOVES-agents.md
	url = https://github.com/POWERFULMOVES/PMOVES-agents.md.git
```

No `branch =` line. PR1's `skills/PMOVES-skills` entry DID have `branch = main` because... hmm, looking at the commit, it must have been edited post-`git submodule add` too. Actually I can't see the individual PR1 commits (they were squashed into `d4af79f325`); only the resulting tree shows `branch = main` on the entries. So either the PR1 author edited it post-add, or the squashed-merge commit had it that way.

**The decision:** edit `.gitmodules` after the `git submodule add` to add the `branch = main` line. Then `git add .gitmodules` to stage the change. Net effect is identical to having done `git submodule add -b main URL PATH`.

**Rule of thumb:** if the operator/spec requires `branch = main` in the .gitmodules entry, do the add then edit the entry. If you don't care which branch the submodule tracks (the default HEAD is fine), use `git submodule add` as-is. The `branch =` field is a *tracking preference* (where `git submodule update --remote` pulls from) - if the upstream default branch renames, the submodule stops following. For tier-2+ always-relevant docs, this is a real concern.

### 2.2 The `### PMOVES-agents.md` subsection was already in `.claude/context/submodules.md` as bullet-form before this PR

**The pre-existing state:** looking at lines 87-93 of submodules.md (pre-PR3), there was already a `### PMOVES-agents.md` subsection with bullet-form metadata (Path, Repository, Upstream, Purpose, Tier, Cross-refs). The skill constellation `### skills/ — Skills Constellation` subsection (lines 95-108) below it used table-form.

**The decision:** add a one-row table inside the `### PMOVES-agents.md` subsection, mirroring the `skills/*` table format. The bullets stay (they have the detailed Tier + Cross-refs info); the new table provides scannable parity with the skills/* entries.

**The alternative considered:** convert the existing bullets to a single-row table. Decided against it - would lose the detailed Tier and Cross-refs lines, and the bullets + table together read better than either alone.

**Rule of thumb:** when an existing docs section has both a "detailed" and "scannable" representation, the natural PR-time add is a scannable sibling, not a replacement. The detail is for context (path, repo, purpose, tier, cross-refs); the scannable form is for navigation. Both serve.

### 2.3 The submodule_skill_registry.json "Total submodules: 54" line is stale (actual count is 58 post-PR3)

**The observation:** the `.claude/context/submodules.md` line 11 says "Total submodules: 54 (including vendor/legacy dual-mounts; +5 in `skills/` after Phase 2)". The actual count from the JSON registry is 58 after this PR (57 before, +1 for PMOVES-agents.md). The 54 is the Phase-2 count, not the current count.

**The decision:** do NOT touch the "54" line as part of this PR. It's a pre-existing staleness that's been accumulating for a while (a dozen+ submodules have been added since Phase 2 without updating the line). Fixing it is a separate cleanup slice (would need a fork-by-fork audit of "what's the actual current count of distinct submodules, including dual-mounts, including skills/*, etc.").

**Rule of thumb:** stay in scope. If a count is stale, document the staleness in the LEARNINGS file but don't fix it in an unrelated PR.

### 2.4 The "agents.md" fork convention - top-level (not under `skills/`)

**The pattern:** the `skills/` tree is for **runtime-invokable agent skills** - skills that an agent can `bash`, `read`, or `write` to do work (e.g., the `claude-d3js-skill` lets an agent produce D3.js charts; the `agent-sandbox-skill` lets an agent spin up an isolated execution environment; the `Pmoves-skills` is the post-recenter home of the canonical skills library).

**The `PMOVES-agents.md` fork is different:** it's a **format/taxonomy reference** - the agents.md open spec (a doc, not a skill), the agent taxonomy docs, and the persona schema docs. Agents don't *invoke* it; they *load* it when format/taxonomy/persona work is in scope (Tier-2 always-relevant).

**The decision:** place `PMOVES-agents.md/` at the repo root (not under `skills/`). This matches its function (format reference, not runtime skill) and matches the operator's spec.

**Rule of thumb:** new forks of format/taxonomy/persona/spec repos go at the repo root, not under `skills/`. The `skills/` tree is for runtime-invokable skills only.

### 2.5 PR1 already added a `skills/PMOVES-skills` entry - don't duplicate

**The context:** PR1 added `skills/PMOVES-skills/` (a fork of `vercel-labs/skills`, the post-recenter home of the skills library that moved from `MiniMax-AI/skills`). This PR adds `PMOVES-agents.md/` (a fork of `agentsmd/agents.md`, the AGENTS.md format open spec). The two are different upstreams and different purposes, even though both are "agents" content.

**The decision:** the `PMOVES-agents.md` entry in the registry is a separate entry from `skills/PMOVES-skills`. They are not duplicates. The cross-reference is in the docs (the root `AGENTS.md` file mentions the format spec at `PMOVES-agents.md/`; the skills constellation docs mention the library at `skills/PMOVES-skills/`).

**Rule of thumb:** distinct upstreams get distinct registry entries, even if both are "agents" content. The `domain_tags` overlap is fine; the entry identity is by fork path.

## 3. Wrong-suggestion / Already-addressed (none this slice)

No review threads yet - this is a pre-review LEARNINGS capture. If codex/CodeRabbit surfaces findings, they'll be appended to the 4-bucket taxonomy below.

## 4. Cross-refs

- `AGNOTE4482PHI.t1.md` row `Mavis::AGENTS-MD-FOLDIN::2026-08-17` - the CLAIM (this commit)
- `.claude/context/submodules.md` `### PMOVES-agents.md` section - the canonical doc for the submodule (updated with sibling table row)
- `pmoves/configs/submodule_skill_registry.json` `PMOVES-agents.md` entry - the context-tag injector map
- Root `AGENTS.md` - the file that follows the format spec at `PMOVES-agents.md/`
- PR1 of the fold-in: `agents_md_foldin_pr1_LEARNINGS.md` at `d4af79f325` - the skills fold-in LEARNINGS file
- PR2 of the fold-in: `mcpcli_foldin_pr2_LEARNINGS.md` (pending, separate worktree) - the MCP+CLI+Provider-Verifier fold-in LEARNINGS file
