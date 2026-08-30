# LEARNINGS — 6-repo fold-in PR1 (skills fold-in: PMOVES-skills)


> **CORRECTION (2026-08-20).** The "recentering" premise below is wrong. `MiniMax-AI/skills` never moved to `vercel-labs/skills` — both are alive, share no history, and are different kinds of thing (a 17-skill MIT *collection* vs the "npx skills" *tool*). `Pmoves-Minimax-skills` is therefore NOT deprecated; it is a live source, now tracked at `PMOVES-skills/sources/`. Kept as written otherwise, since this records what was believed at the time. See `skills/README.md` § Correction.

> Per the 4-bucket taxonomy (missed-signal / fix-pattern / wrong-suggestion / already-addressed).
> Captured during implementation, before any review. Add more buckets as review threads land.

## 1. The slice as a whole

**Goal:** fold 6 upstream forks into PMOVES.AI as proper submodules, one slice per "logical group". Operator chose **3 separate PRs** for revert granularity (PR1=skills, PR2=MCP+CLI+Provider-Verifier, PR3=agents.md). This file covers **PR1 (skills fold-in)**.

**3 stacked commits on `feat/skills-foldin-pmovesskills` (off `c5845f1a3e` = main @ 2026-08-17):**

| # | SHA | What |
|---|-----|------|
| 1 | `a16d2adaa2` | feat(submodule): fold in PMOVES-skills — `.gitmodules` + new `skills/PMOVES-skills` gitlink + 1-commit bump on `skills/Pmoves-skills` (caught during the add) + `skills/README.md` constellation row + recenter note |
| 2 | `316c089e9c` | docs(context): register PMOVES-skills in `.claude/context/submodules.md` table + `pmoves/configs/submodule_skill_registry.json` |
| 3 | (pending) | docs(agnote): AGNOTE CLAIM row + this LEARNINGS file |

**Acceptance criteria status:**

| # | Criterion | Status |
|---|-----------|--------|
| 1 | `skills/PMOVES-skills/` exists as a gitlink at the upstream HEAD | Done (commit 1) |
| 2 | `.gitmodules` has the entry (url=POWERFULMOVES/PMOVES-skills, branch=main) | Done (commit 1) |
| 3 | `skills/README.md` constellation table has the new row + recenter note | Done (commit 1) |
| 4 | `.claude/context/submodules.md` table has the new row | Done (commit 2) |
| 5 | `pmoves/configs/submodule_skill_registry.json` has the new entry (context_tier=2, domain_tags=agents+mcp) | Done (commit 2) |
| 6 | AGNOTE CLAIM row appended | Done (commit 3) |
| 7 | JSON parses | Verified with `python -c "import json; json.load(...)"` |
| 8 | 3-PR strategy adopted (not 1 mega-PR or 6 micro-PRs) | Per operator choice (3 separate PRs for revert granularity) |

**Out of scope (intentional, lives in other PRs of the fold-in):**

- `POWERFULMOVES/Pmoves-Minimax-skills` (deprecated pre-recenter URL) — preserved as a `skills/README.md` reference, not a separate submodule. The recenter note explains why.
- `PMOVES-agents.md` — PR3.
- The 3 MCP+CLI+Provider-Verifier repos — PR2.

## 2. Patterns / fixes

### 2.1 `git submodule add` refreshes existing entries — expect minor bumps

**The trap:** when adding a new nested submodule, `git submodule add` also fetches the existing siblings. If an upstream had a new commit since the last fetch, the existing entry's gitlink advances. The 1-commit bump on `skills/Pmoves-skills` (`69c0b1a` → `c6f69c6`) was caught this way.

**The decision:** include the minor bump in this PR (it was the add operation that fetched it, so the diff is the same change). Splitting it would have meant a separate "rebase onto main" or "submodule update" PR for a 1-commit bump, which is more noise than signal.

**Rule of thumb:** if the bump is ≤ 3 commits and the add operation is what fetched it, include it in the same PR. Document it in the commit message. If it's > 3 commits or from an unrelated upstream, split it.

### 2.2 PMOVES-skills recenter — `MiniMax-AI/skills` → `vercel-labs/skills` (August 2026)

**The change:** the skills library that was at `MiniMax-AI/skills` was recentered to `vercel-labs/skills`. The POWERFULMOVES fork followed the move; the canonical home is now `POWERFULMOVES/PMOVES-skills` (tracking `vercel-labs/skills` main). The pre-recenter URL (`POWERFULMOVES/Pmoves-Minimax-skills` tracking `MiniMax-AI/skills`) is preserved as a deprecated reference.

**Why not add `Pmoves-Minimax-skills` as a separate submodule:** it would split the work in two when one is the post-recenter of the other. The `skills/README.md` recenter note documents the deprecated URL for anyone with bookmarks or scripts that still point at it. If a separate entry is wanted later, add it as `skills/Pmoves-Minimax-skills/` with a "Deprecated" status row.

**Rule of thumb:** when an upstream recenters, the canonical fork follows; deprecated URLs are documented in the existing module's README, not added as separate submodules.

### 2.3 Skills constellation README is the canonical doc for the constellation

**The structure (post-update):**

1. **Tier 2** declaration — load README first, then specific submodule docs only when working in that skill's domain
2. **Constellation table** — 6 rows now (5 from the 2026-05-09 + 1 added 2026-08-17); columns: Submodule / Path / Upstream / Purpose / Status
3. **Recentering note** — paragraph explaining the `MiniMax-AI` → `vercel-labs` move
4. **Adding more skill forks (future)** — the untrusted-code-integration boundary procedure (damage-control allowlist + per-URL Bash-tool authorization)
5. **Activation paths** — how each skill becomes available to a Claude Code session
6. **KiloCode skills** — separate native directory (`.kilocode/skills/`)
7. **Cross-references** — links to other docs

**Rule of thumb:** when adding a skill fork, update all 4 touch points — the constellation table, the activation paths section (if applicable), `.claude/context/submodules.md` table, and `pmoves/configs/submodule_skill_registry.json`. The README is the user-facing doc; the other 3 are the context-loader side.

### 2.4 Nested submodules follow `skills/<fork-name>/` path convention

**The convention:** all 6 entries in the constellation are at `skills/<fork-name>/`, not at the repo root. This keeps the constellation discoverable as a single group and matches the existing `skills/` directory layout.

**Rule of thumb:** new skill forks go under `skills/`, not at the repo root. The repo-root convention is reserved for first-tier forks (Agent Zero, Archon, etc.).

## 3. Wrong-suggestion / Already-addressed (none this slice)

No review threads yet — this is a pre-review LEARNINGS capture. If codex/CodeRabbit surfaces findings, they'll be appended to the 4-bucket taxonomy below.

## 4. Cross-refs

- `AGNOTE4482PHI.t1.md` row `Mavis::SKILLS-FOLDIN::2026-08-17` — the CLAIM
- `skills/README.md` — the canonical constellation doc
- `.claude/context/submodules.md` — the registry table
- `pmoves/configs/submodule_skill_registry.json` — the context-tag injector map
- The other 2 PRs of the 6-repo fold-in (MCP+CLI+Provider-Verifier, agents.md) — pending
