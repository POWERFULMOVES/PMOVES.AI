# Submodule Fleet Audit — 2026-05-18

**Lane:** Submodule sync + worktree cleanup (Z890-CLAUDE per AGNOTE4482PHI.t1.md 2026-05-18 lane attribution)
**Produced by:** Z890-CLAUDE via `pmoves-submodule-fleet` skill
**Shared attribution:**
- **5090-CLAUDE** offered a read-only state snapshot in their 2026-05-18 lane-respect ACK; this audit fulfills that offer using the dedicated skill, freeing 5090 for other work (PR #1522 / #1523 + activation cascade waiting on env.shared fix).
- **Skill author** (whoever shipped `pmoves-submodule-fleet`) — script lives at `.claude/skills/pmoves-submodule-fleet/scripts/fleet_audit.sh`.

Per DARKXSIDE 2026-05-18: *"ensure its noted shape attribution is shared we are all working towards same overall goals MOF will make collabing much easier once live."*

**Raw output:** [`SUBMODULE_FLEET_AUDIT_2026-05-18.txt`](./SUBMODULE_FLEET_AUDIT_2026-05-18.txt) (116 lines, full recursive enumeration).

---

## Tally

| Category | Count | Meaning |
|---|---:|---|
| Total submodules (recursive) | 112 | Includes nested `external/`, `features/`, `pmoves_multi_agent_pro_pack/` |
| Clean (behind=0, dirty=n) | 30 | No action |
| Small drift (behind 1-100) | 72 | Candidates for batch promotion |
| Dirty working tree | 7 | Disposition required before promote |
| Large drift (behind > 100) | 3 | Investigate before any move |

`★ Insight ─────────────────────────────────────`
- 30 clean / 112 total = ~27% — fleet is mostly drifted but mostly recoverable
- The "uninit" lines are submodules that exist in `.gitmodules` but aren't checked out locally; that's expected for some (reference repos) and a real gap for others (skills/* per CLAUDE.md line 42-43)
- 5090-CLAUDE's earlier snapshot showed 12 top-level dirty submodules; this audit shows 7 dirty across the full recursive set. The difference: 5090 listed top-level pointer drift markers (M/m), this skill measures content+pointer drift recursively — different shapes, both valid
`─────────────────────────────────────────────────`

## Operator-attention cases (read these first)

### 1. PMOVES-ClawZ — behind=27980 (huge)

This is almost certainly **not** a 27980-commit gap. Three plausible causes:
- Working-tree HEAD is on a wildly different branch / fork's history (e.g., upstream `openclaw/openclaw` master vs PMOVES fork)
- Force-push upstream rewrote history; the "behind" count compares against a remote whose ancestor walk doesn't reach our local commit
- 5090-CLAUDE flagged ClawZ earlier as "working ref behind merge commit f05fd3f5 (PR #1 integration merge)" — possible the comparison branch is wrong

**Do NOT auto-promote ClawZ.** Operator + 5090-CLAUDE call.

### 2. PMOVES-Archon/external/PMOVES-Agent-Zero — behind=394

Nested copy of Agent-Zero inside Archon. Top-level Agent-Zero only 3 behind. Either Archon's vendored copy is stale or it's tracking a different upstream. Worth investigating before promoting Agent-Zero.

### 3. PMOVES-Headscale — behind=270

Significant drift. Top-level submodule.

### 4. PMOVES-Neo4j, PMOVES-space-agent — behind=?

`git fetch` failed or comparison branch couldn't be resolved. Possibly new submodules or repos with non-standard default branch. **PMOVES-space-agent** wasn't in 5090's earlier snapshot — may be a new addition this session.

### 5. Dirty working trees (7 total)

| Path | Behind | Notes |
|---|---|---|
| PMOVES-Jellyfin | 0 | Content changes with NO pointer drift — local edits inside the submodule? |
| Pmoves-hyperdimensions | 0 | Same pattern — local content changes |
| skills/PMOVES-agent-sandbox-skill | 2 | `uninit` + dirty — initialization gap |
| skills/PMOVES-awesome-agent-skills | 2 | same |
| skills/Pmoves-claude-d3js-skill | 2 | same |
| skills/Pmoves-skills | 2 | same |
| skills/pmoves-fork-repository-skill | 2 | same |

**Skills constellation gap:** all 5 skills/* show `uninit + dirty + behind=2`. Per `.claude/CLAUDE.md:42-43`: *"run `git submodule update --init skills/` to populate"*. The dirty status is likely because Pinokio's skill loader wrote content into those paths without git knowing — explains why new skills (e.g., `pmoves-submodule-fleet`) appeared mid-session. Single fix: `git submodule update --init skills/` will reconcile.

## Promotion-safe set (small drift, no dirty, no special cases)

These ~25 submodules can be batched into a single `chore(submodules): promote N pointers` commit once the parent branch is sync'd to main:

| Submodule | Behind |
|---|---:|
| PMOVES-A2UI | 8 |
| PMOVES-Agent-Zero | 3 |
| PMOVES-AgentGym | 3 |
| PMOVES-BotZ-gateway | 1 |
| PMOVES-DoX | 4 |
| PMOVES-E2B-Danger-Room | 19 |
| PMOVES-E2B-Danger-Room-Desktop | 1 |
| PMOVES-E2b-Spells | 4 |
| PMOVES-Open-Notebook | 1 |
| PMOVES-Pinokio-Ultimate-TTS-Studio | 1 |
| PMOVES-Wealth | 6 |
| PMOVES-a0-plugins | 1 |
| PMOVES-llama-throughput-lab | 1 |
| PMOVES-n8n | 1 |
| PMOVES-supabase | 1 |
| PMOVES-tensorzero | 1 |
| PMOVES-transcribe-and-fetch | 13 |
| PMOVES-BoTZ | 10 |

**Open question:** PMOVES-transcribe-and-fetch was previously flagged (2026-05-01 audit) as having upstream history rewritten — `origin/main` pointer commit missing in submodule. Need to re-verify with `git -C PMOVES-transcribe-and-fetch log` before promoting. If still broken: cipher-style upstream republish needed.

## Action sequence (proposed, operator approval before destructive ops)

1. **`git submodule update --init skills/`** — resolves the skills constellation initialization gap (single command, low risk).
2. **Stash restore** — z890-claude session stash `z890-session-submodule-pointer-bumps-2026-05-18` holds 23 prior submodule pointer bumps; review against this audit before keeping or dropping.
3. **Disposition for 7 dirty working trees** — diff each submodule, decide commit-to-submodule vs revert. Skills constellation handled in step 1.
4. **PMOVES-ClawZ investigation** — operator + 5090-CLAUDE. Out of this lane until they signal.
5. **PMOVES-Neo4j + PMOVES-space-agent fetch retry** — explicit `git -C <sub> fetch origin && git -C <sub> branch -r` to see remote branches; may need manual upstream URL fix.
6. **Batch promotion PR** — once 1-5 settle, single `chore(submodules): promote ~25 small-drift pointers` PR off main.

## Why this is read-only

`pmoves-submodule-fleet/scripts/fleet_audit.sh` is informational: best-effort `git fetch --quiet origin`, then `git rev-list --count HEAD..origin/main` for the behind count. **No destructive ops, exits 0 regardless of drift.**

Promotion, init, reset, and dirty-tree disposition are all SEPARATE steps that need operator authorization per `feedback_check_worktree_before_remove.md`. This audit only provides the map.

---

## Cross-references

- `.claude/skills/pmoves-submodule-fleet/SKILL.md` — skill spec + when to use
- `pmoves/docs/operations/MISSING_LINC_FINDINGS.md` — MLF-006 (offline ai-lab runner) + MLF-002 (stale worktrees holding legacy CHIT path) overlap with this lane
- `pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md` § Active Claim Register — 2026-05-18 Z890-CLAUDE entry takes this lane
- `pmoves/docs/AGENTS/AGNOTE4482PHI.5090-SUBMODULE-AUDIT.md` — 5090-CLAUDE's canonical 2026-03-21 28→0 drift precedent; pattern source for batch promotion
- 5090-CLAUDE's 2026-05-18 lane-respect snapshot (delivered via DARKXSIDE relay) — top-level pointer view; this doc is the recursive deep view of the same fleet state
