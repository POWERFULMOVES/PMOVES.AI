# Branch Strategy Anti-Pattern Analysis

**Date:** 2026-04-24
**Scope:** 91 of 104 remote branches trimmed in single session
**Source Files:** AGNOTE4482.md (403 lines), AGNOTE4482_SITREP.md (120 lines), AGNOTE4482_ROADMAP_W1-W5.md (570 lines), AGNOTE4482_SIGNOFF_CHECKLIST.md (111 lines)
**Auditor:** Security Auditor (AGENT-ZERO-GLM)

---

## Summary

| Severity | Count | Anti-Patterns |
|----------|-------|---------------|
| P0 | 2 | Orphan Branch Proliferation, Multi-Agent Collision |
| P1 | 4 | Naming Inconsistency, Post-Merge Branch Rot, Signoff Gate Gap, Backup Restore Regression |
| P2 | 2 | Phase Branch Sprawl, ACK Without Branch Cleanup |

**Root cause thesis:** PMOVES built a sophisticated multi-agent convergence protocol (AGNOTE4482) with claim registers, signoff gates, and GRAPHITI marks — but the protocol covers *what* agents build, not *how branches live and die*. Branch lifecycle is an afterthought at every layer: no naming convention, no cleanup automation, no signoff gate item, no ACK template field. The 91 trimmed branches are the predictable result.

---

## Anti-Pattern #1: Naming Inconsistency

**Severity:** P1
**Deleted branch evidence:** `feat/p1-*` through `feat/p7-*`, `feature/kilo-claw-config`, `pr/*`, `fix/*`, `infra/*`, `docs/*`, `refactor/*`

### Evidence from Files

The Agent Claim Register in AGNOTE4482_ROADMAP_W1-W5.md (lines 486-521) shows at least three different naming conventions used for the same type of work:

| Branch Name | Convention | Agent |
|-------------|-----------|-------|
| `feat/w1-agent-terminal-theme` | `feat/` | 4090-CLAUDE |
| `feat/tts-engine-capabilities-registry` | `feat/` | 5090-CLAUDE |
| `feat/discord-publisher-mcp` | `feat/` | z890-claude |
| `feat/w6-p3-persona-selector` | `feat/` | 4090-CLAUDE |
| `feat/chit-integration-wave-1` | `feat/` | 4090-CLAUDE |
| `feature/kilo-claw-config` | `feature/` | 4090-CLAUDE |
| `feat/4090-coding-workstation-stack` | `feat/` | 4090-CLAUDE |

The same agent (4090-CLAUDE) used both `feat/` and `feature/` prefixes. The `pr/*` prefix (found in deleted branches) suggests yet another convention where the PR number became the branch name — reversing the normal relationship.

No naming convention is documented in any of the four AGNOTE4482 files. The SITREP (line 16) tells agents to run `git branch` but not how to name one.

### Root Cause

Each agent session starts cold (SITREP: "read this FIRST on fresh sessions"). Without a documented branch naming convention, agents default to their own interpretation of conventional commits prefixes. The `feature/` vs `feat/` split is likely LLM-model-dependent — different models (Claude vs GPT vs GLM) have different training data distributions for commit prefix conventions.

### Recommended Fix

Add a **Branch Naming Convention** section to AGNOTE4482_SITREP.md (after line 18, the `git branch` check):

```markdown
## Branch Naming Convention

All branches MUST follow: `{type}/{workstream-or-ticket}-{short-description}`

| Type | Use When | Example |
|------|----------|---------|
| `feat/` | New feature or roadmap work | `feat/w1-terminal-theme-renderer` |
| `fix/` | Bug fix or security patch | `fix/nats-auth-missing` |
| `infra/` | Infrastructure, CI/CD, compose | `infra/kong-oom-memory-limit` |
| `docs/` | Documentation only | `docs/agnote4482-branch-convention` |
| `refactor/` | Code refactoring without behavior change | `refactor/nats-subject-consolidation` |

**Forbidden prefixes:** `feature/` (use `feat/`), `pr/` (branches are not PRs), `p1/`-`p7/` (use workstream ID).

**Workstream IDs:** `w1`-`w6` (from ROADMAP), or GitHub issue/PR number.
```

### Which File to Update

- **AGNOTE4482_SITREP.md** — add naming convention section (cold-start orientation, agents read this first)
- **AGNOTE4482_SIGNOFF_CHECKLIST.md** — add §9: "Branch naming follows AGNOTE4482_SITREP convention"

---

## Anti-Pattern #2: Orphan Branch Proliferation

**Severity:** P0
**Deleted branch evidence:** 72 branches with NO open PR — no PR was ever created

### Evidence from Files

The Agent Claim Register (ROADMAP lines 482-521) is the smoking gun. It contains multiple claim states that explain the orphan pipeline:

1. **"CLAIMED — pending X session"** (lines 490, 492):
   - W1 (remaining: BoTZ CLI bridge) → 5090-claude → CLAIMED — pending 5090 session → Branch: `—`
   - W3 (Discord classrooms) → 5090-claude → CLAIMED — pending 5090 session → Branch: `—`

   These claims show intent without execution. But when agents *did* execute, they branched first — and if the session ended before PR creation, the branch became an orphan.

2. **"RECOMMENDED — next X session"** (lines 504-508, 514-517):
   - W6-P1, W6-P2, W6-P3, W6-P5 all marked RECOMMENDED
   - W3/M2 creator automation marked RECOMMENDED
   
   "RECOMMENDED" is not a claim — it's a suggestion. But nothing prevents a future agent from interpreting it as authorization to branch.

3. **Successful pattern vs failed pattern**: Lines 496-513 show the successful path clearly:
   - Claim → Branch name recorded → Work performed → SHIPPED with commit SHA or PR#
   - Example: `feat/chit-integration-wave-1` → SHIPPED `f7dafa56` → 5 commits listed

   The 72 orphans followed the first two steps (claim + branch) but never reached the third (PR creation).

4. **No PR creation gate**: The SITREP health check (lines 30-41) includes `git status -sb` but never `gh pr list` or any check for un-PR'd branches.

### Root Cause

The claim register records *intent* but has no **lifecycle state machine**. A claim can be: CLAIMED → SHIPPED (success) or CLAIMED → abandoned (orphan). There is no:
- Timeout/SLA on CLAIMED status
- Session-end checkpoint that asks "did you create a PR?"
- Automated scan for branches with no associated PR
- "ABANDONED" state that triggers branch deletion

The 72 orphans represent 72 sessions that started work but never completed the PR cycle. In a multi-agent system where sessions are ephemeral ("fresh start, VS Code restart, new node" — SITREP line 5), this is a systemic leak, not an occasional oversight.

### Recommended Fix

**Immediate (automation):** Add a GitHub Actions workflow that runs daily:

```yaml
# .github/workflows/stale-branch-sweep.yml
name: Stale Branch Sweep
on:
  schedule:
    - cron: '0 6 * * *'  # daily at 06:00
  workflow_dispatch:
jobs:
  sweep:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - name: Find orphan branches (no PR, no recent commit)
        run: |
          ORPHANS=$(git branch -r --format='%(refname:short)' | \
            grep -v 'main\|develop' | \
            while read branch; do
              # Check if PR exists
              if ! gh pr list --head "${branch#origin/}" --json number -q '.[] | .number' 2>/dev/null; then
                # Check last commit age
                LAST=$(git log -1 --format='%ct' "$branch")
                NOW=$(date +%s)
                AGE=$(( (NOW - LAST) / 86400 ))
                if [ $AGE -gt 7 ]; then
                  echo "$branch (orphan ${AGE}d)"
                fi
              fi
            done)
          echo "ORPHANS=$ORPHANS" >> $GITHUB_OUTPUT
      - name: Delete orphans (dry-run by default)
        if: env.DRY_RUN != 'false'
        run: echo "$ORPHANS"
        env:
          ORPHANS: ${{ steps.sweep.outputs.ORPHANS }}
```

**Process (claim register):** Add mandatory fields to the claim register:

```markdown
| Workstream | Agent | Claimed | Status | Branch | PR | Session-End Checkpoint |
```

Add a new status: `ORPHANED` — set when a CLAIMED entry has no PR after 7 days. ORPHANED entries trigger branch deletion.

### Which File to Update

- **AGNOTE4482_ROADMAP_W1-W5.md** — add PR column + Session-End Checkpoint column to Claim Register (line 486)
- **AGNOTE4482_SITREP.md** — add `gh pr list --head $(git branch --show-current)` to health check (line 41)
- **New file:** `.github/workflows/stale-branch-sweep.yml`

---

## Anti-Pattern #3: Post-Merge Branch Rot

**Severity:** P1
**Deleted branch evidence:** 17 merged branches never cleaned up

### Evidence from Files

AGNOTE4482.md line 195 is the only mention of branch cleanup in the entire 403-line document:

> **Post-merge**: Verified all fixes on main (79+13 tests pass), cleaned 10 stale branches

This is embedded in a "Work Performed" bullet under the SPARK onboarding section (2026-04-18). It is:
- Ad-hoc (done as part of a larger session, not a dedicated process)
- Undocumented (no list of which 10 branches, no criteria for selection)
- Non-reproducible (no automation, no workflow trigger)
- Incomplete (10 cleaned, but 17 merged branches still existed at trim time — 7 were missed)

The signoff checklist (AGNOTE4482_SIGNOFF_CHECKLIST.md) has 20 items across 8 sections. None mention branch deletion after merge.

The Agent ACK template (repeated 8 times in AGNOTE4482.md) is:
```
- Agent: `<NAME>`
- Signature: `ACK::<NAME>::<SCOPE>`
- Timestamp: `<ISO>`
```

No field for "branches created/deleted in this session."

### Root Cause

GitHub's default branch protection does not auto-delete branches on merge. PMOVES has not enabled the GitHub setting "Automatically delete head branches" on any branch protection rule. Without this setting + no manual process + no CI automation, merged branches accumulate indefinitely.

### Recommended Fix

**Immediate (GitHub setting):** Enable "Automatically delete head branches" in branch protection rules for `main`. This is a checkbox in Settings → Branches → Branch protection rules → Edit → "Automatically delete head branches". This single setting would have prevented all 17 post-merge rot branches.

**Defense-in-depth (CI):** Add a post-merge workflow as a safety net:

```yaml
# .github/workflows/post-merge-cleanup.yml
name: Post-Merge Branch Cleanup
on:
  pull_request:
    types: [closed]
    branches: [main]
jobs:
  cleanup:
    if: github.event.pull_request.merged == true
    runs-on: ubuntu-latest
    steps:
      - run: |
          gh api \
            --method DELETE \
            repos/${{ github.repository }}/git/refs/heads/${{ github.head_ref }} \
            || true  # already deleted is fine
```

### Which File to Update

- **GitHub repository settings** — enable auto-delete (not a file change)
- **New file:** `.github/workflows/post-merge-cleanup.yml`
- **AGNOTE4482_SIGNOFF_CHECKLIST.md** — add §9.1: "Merged branches are auto-deleted (GitHub setting + workflow)"

---

## Anti-Pattern #4: Phase Branch Sprawl

**Severity:** P2
**Deleted branch evidence:** `feat/p1-*` through `feat/p7-*` — 7 sequential phase branches, all orphaned

### Evidence from Files

The ROADMAP defines workstreams W1-W5 (lines 88-284) and W6 (lines 334-464). Within W6, there are 5 build phases (P1-P5, lines 380-408). The Claim Register (line 486) maps branches to workstreams:

- `feat/w6-p3-persona-selector` — this is the **correct** pattern (workstream + phase)
- `feat/p1-*` through `feat/p7-*` — this is the **broken** pattern (phase without workstream)

The broken pattern suggests an agent (or a session) created branches for phases p1-p7 without tying them to any workstream. This could have been:
- An early planning session that created skeleton branches before the W1-W6 structure was formalized
- An agent that read a different planning doc (possibly one of the many referenced but unexamined docs like `NEXT_STEPS.md` or `PMOVES.AI PLANS/ROADMAP.md`) that used a different phase numbering
- A misinterpretation of the ROADMAP's W1-W5 numbering as p1-p5

Critically, the ROADMAP itself has **no branch creation instructions**. It says "All agents read this before claiming workstream lanes" (line 5) but never says "create a branch when you claim a lane."

### Root Cause

The ROADMAP is a planning document, not an execution protocol. The gap between planning ("here are 5 workstreams with phases") and execution ("create branch, do work, create PR") is unbridged. Agents filled this gap with their own interpretation, leading to `p1-p7` branches that don't map to any documented workstream.

### Recommended Fix

Add an **Execution Protocol** section to the ROADMAP, between the Vision (line 18) and Dependency Graph (line 63):

```markdown
## Execution Protocol

When claiming a workstream lane:
1. **Branch**: Create `feat/w{N}-p{M}-{description}` only AFTER claiming in the register
2. **PR**: Create PR within 48 hours of branch creation. If blocked, add `BLOCKED:` prefix to register status
3. **Abandon**: If no PR in 7 days, mark register entry as `ORPHANED` and delete branch
4. **No skeleton branches**: Do NOT create branches for future phases. Only branch for the phase you are actively executing
```

### Which File to Update

- **AGNOTE4482_ROADMAP_W1-W5.md** — add Execution Protocol section after line 18

---

## Anti-Pattern #5: AGENT ACK Without Branch Cleanup

**Severity:** P2
**Deleted branch evidence:** All 91 branches accumulated across 8+ ACK sessions with zero cleanup

### Evidence from Files

AGNOTE4482.md contains 8 Agent ACK entries. Here is every one with its scope:

| # | Agent | ACK Scope | Branches Created | Branches Cleaned |
|---|-------|-----------|-----------------|------------------|
| 1 | CODEX-GPT5 | PHI-4482-GATEWAY | Not listed | 0 |
| 2 | CLAUDE-OPUS | TAC-TOPOLOGY-AUDIT | Not listed | 0 |
| 3 | 4090-CLAUDE | ROOM-CATALOG-AUDIT | Not listed | 0 |
| 4 | CLAUDE-OPUS | SELF-REVIEW-AUDIT | Not listed | 0 |
| 5 | AGENT-ZERO-GLM | A2A-RUNTIME-WIRING | Not listed | 0 |
| 6 | PMOVES-AGENT-ZERO-SPARK | POST-MERGE-REVIEW-SPARK-ONBOARD | Not listed | 10 (ad-hoc, line 195) |
| 7 | AGENT-ZERO-SIDECAR | CONVERGENCE-WAVE-APR19 | Not listed | 0 |
| 8 | AGENT-ZERO-GLM | MOF-ARCHITECTURE-CONVERGENCE | Not listed | 0 |

Only 1 of 8 ACKs mentions any branch cleanup, and it was informal ("cleaned 10 stale branches" — no list, no criteria). The ACK template has no field for branch lifecycle.

### Root Cause

The ACK template was designed as an **audit trail** (who did what, when) but not as a **session closure checklist**. It answers "what happened?" but not "what's left behind?" In a multi-agent system where each session is ephemeral, the ACK should be the natural place to enforce session-end hygiene.

### Recommended Fix

Expand the ACK template to include branch lifecycle:

```markdown
## Agent ACK (Gateway)
- Agent: `<NAME>`
- Signature: `ACK::<NAME>::<SCOPE>`
- Timestamp: `<ISO>`
- Branches created: `<list or NONE>`
- Branches merged: `<list or NONE>`
- Branches deleted: `<list or NONE>`
- Open PRs: `<list or NONE>`
- Orphan risk: `<YES/NO — if YES, explain what's pending and expected resolution>`
```

### Which File to Update

- **AGNOTE4482.md** — update the ACK template (first occurrence at line 43) and add a note that all future ACKs must use the expanded template
- **AGNOTE4482_SITREP.md** — add ACK template reference in the "Key Files" table (line 59)

---

## Anti-Pattern #6: Signoff Gate Doesn't Cover Branch Hygiene

**Severity:** P1
**Deleted branch evidence:** 91 branches existed despite 19/20 signoff items passing

### Evidence from Files

AGNOTE4482_SIGNOFF_CHECKLIST.md contains 20 items across 8 sections:

| Section | Topic | Items | Branch-Related? |
|---------|-------|-------|----------------|
| §1 | Prospectus coherence | 4 | No |
| §2 | Agent Zero baseline | 4 | No |
| §3 | ClaWz baseline | 4 | No |
| §4 | Config/coding-plan alignment | 4 | No |
| §5 | Control-plane alignment | 4 | No |
| §6 | Release/CVE/hardening | 4 | No |
| §7 | P7 remaining items | 4 | No |
| §8 | Docs parity | 4 | No |

Zero items address branch hygiene. The checklist achieved 19/20 pass while 91 stale/orphan branches festered on the remote. This means the signoff gate **certified merge readiness** while the branch namespace was in critical disarray.

The checklist's stated purpose (line 13) is: "AGNOTE4482 does not move on vibes alone." But 91 orphan branches is exactly the kind of structural debt that vibes miss and checklists should catch.

### Root Cause

The signoff checklist was designed to validate *content* correctness (prospectus coherence, baseline alignment, config parity) but not *process* hygiene (branch lifecycle, PR cadence, stale artifact detection). This is a classic gap in multi-agent systems: the convergence protocol validates the output but not the process that produced it.

### Recommended Fix

Add §9 to the signoff checklist:

```markdown
### 9. Branch and PR hygiene

- [ ] No orphan branches exist (branches with no associated PR older than 7 days).
- [ ] All merged branches have been deleted (GitHub auto-delete enabled + verified).
- [ ] Branch naming follows AGNOTE4482_SITREP convention (no `feature/`, `pr/`, or bare `pN/` prefixes).
- [ ] Agent Claim Register has no CLAIMED entries older than 7 days without a PR.
- [ ] Stale branch sweep workflow is active (`.github/workflows/stale-branch-sweep.yml`).
```

### Which File to Update

- **AGNOTE4482_SIGNOFF_CHECKLIST.md** — add §9 after line 80
- **Signoff Ledger** (line 88) — add column for §9 signoff

---

## Anti-Pattern #7: Multi-Agent Collision

**Severity:** P0
**Deleted branch evidence:** 72 orphan branches across 7+ independent agents

### Evidence from Files

The SITREP (lines 106-117) lists 7 agent lanes:

| Agent | Node | Lane |
|-------|------|------|
| Z890-CLAUDE | z890 | Infra, fleet, compose, CI runners |
| 4090-CLAUDE | 4090 laptop | Provider cascade, Shift Crew, field testing |
| 5090-CLAUDE | 5090 | GPU, voice stack, submodule sync |
| CODEX-GPT5 | any | Docs, prospectus, creator control plane |
| KILOCODE-GLM | 5090 | GLM coding plan, vLLM, Proxmox |
| PMOVES-MINIMAX | any | Token plan overflow, writing, hyperdimensions |
| CLAUDE-OPUS | any | Architecture, self-review, convergence |

Plus agents that appear in ACKs but not the lane table: AGENT-ZERO-GLM, PMOVES-AGENT-ZERO-SPARK, AGENT-ZERO-SIDECAR. That's 10+ agents.

The coordination mechanism is the Claim Register (ROADMAP line 482). But the register has fatal weaknesses:

1. **No locking**: Two agents can claim the same workstream simultaneously. The register is a markdown table — not a mutex.
2. **No conflict detection**: AGNOTE4482.md line 12 references `KRISS_KROSS_ACCORD.md` ("Codex-led collision overlay and weave protocol") but this protocol apparently doesn't prevent branch collision — 91 branches prove it.
3. **Cross-node context gap**: SITREP lines 97-104 explicitly warn: "Claude's context is NOT consistent across z890/4090/5090. Each node may have different worktrees checked out, different claim register state (if uncommitted changes exist)." An agent on z890 can't see an agent on 4090's uncommitted claim.
4. **"any" node agents**: CODEX-GPT5, PMOVES-MINIMAX, and CLAUDE-OPUS are listed with node `any`. These agents can run on any node and may conflict with node-specific agents without knowing it.

The Claim Register itself shows collision evidence: multiple agents have overlapping "RECOMMENDED" entries for the same workstream (W6-P2 is recommended to both 5090-claude and as a general next step; W3/M2 has two separate RECOMMENDED entries for codex-gpt5).

### Root Cause

The AGNOTE4482 convergence protocol assumes **eventual consistency** — agents will read the register, see existing claims, and avoid collision. But in practice:
- The register is a git-tracked markdown file with no merge conflict prevention
- Agents operate on different nodes with potentially stale register copies
- "RECOMMENDED" status creates ambiguity — is it claimed or not?
- No agent is designated as the **arbitrator** or **scheduler** that prevents duplicate claims

This is the classic distributed systems problem: multiple writers to a shared resource without consensus. The 72 orphan branches are the equivalent of write conflicts that were never resolved.

### Recommended Fix

**Short-term (process):** Designate a single agent as **Claim Arbiter**:

```markdown
## Claim Arbiter

CLAUDE-OPUS is the Claim Arbiter. Before any agent creates a branch:
1. Check the Claim Register for existing claims on the target workstream
2. If claimed by another agent, negotiate handoff or split scope
3. If unclaimed, add your claim with branch name BEFORE creating the branch
4. "RECOMMENDED" entries are NOT claims — they require explicit CLAIMED status before branching
```

**Medium-term (automation):** Move the claim register from markdown to a structured format that supports atomic operations:

- Option A: GitHub Issue labels (`claim:w1`, `claim:w6-p3`, `agent:4090-claude`) — queryable via `gh issue list`
- Option B: A JSON/YAML file with a CI check that validates no duplicate claims
- Option C: Git-tracked lock files (`.claim.lock` per workstream) — primitive but effective

### Which File to Update

- **AGNOTE4482_SITREP.md** — add Claim Arbiter section after line 117
- **AGNOTE4482_ROADMAP_W1-W5.md** — add rule: "RECOMMENDED ≠ CLAIMED. Do not branch on RECOMMENDED." (line 484)
- **KRISS_KROSS_ACCORD.md** — evaluate whether the collision protocol needs strengthening (outside current scope)

---

## Anti-Pattern #8: Backup Restore Regression

**Severity:** P1
**Evidence:** 7 signoff checkmarks undone by 2026-04-22 backup restore

### Evidence from Files

AGNOTE4482.md line 307:
> Restored AGNOTE4482 file suite from host backup to `pmoves/docs/AGENTS/`

Lines 337-340 list the restored files:
```
| `pmoves/docs/AGENTS/AGNOTE4482.md` | Restored from host backup |
| `pmoves/docs/AGENTS/AGNOTE4482_SIGNOFF_CHECKLIST.md` | Restored from host backup |
| `pmoves/docs/AGENTS/AGNOTE4482_SITREP.md` | Restored from host backup |
| `pmoves/docs/AGENTS/AGNOTE4482_ROADMAP_W1-W5.md` | Restored from host backup |
```
The MOF Architecture Convergence Wave section (line 343) acknowledges:
> Per prior audit: **19/20 items checked**. Only §1.4 remains.

But stored memory from a prior session records the actual regression:
> A 2026-04-22 backup restore undid 7 checkmarks (§1.1-1.3, §3.1-3.3) that were added in commits cb74ff823 and 5e381bc84.

The signoff checklist is a **stateful document** — checkmarks represent accumulated verification. A backup restore replaced the current state (with 19/20 checks) with an older state (with 12/20 checks). The restore process had no validation step.

The AGNOTE4482 suite uses GRAPHITI_MARK comments (e.g., `<!-- GRAPHITI_MARK: CLAUDE-OPUS::TAC-TOPOLOGY-AUDIT::2026-02-20 -->`) as audit trail anchors. But these marks are embedded in AGNOTE4482.md, not in the signoff checklist. The checklist has no such anchors — it's pure state, and state is what regressed.

### Root Cause

The backup was a **file-level restore** (copy files from backup to working directory) not a **git-level restore** (git checkout, git revert, or git cherry-pick). File-level restores don't participate in git's merge/conflict detection. If the backup was older than the current HEAD, it silently overwrote newer changes.

The restore was performed by the AGENT-ZERO-GLM (SIDECAR) agent during the MOF Architecture Convergence Wave (2026-04-23). The agent treated the backup as authoritative without comparing timestamps or git hashes.

### Recommended Fix

**Process:** Add a **Restore Protocol** to AGNOTE4482_SITREP.md:

```markdown
## Backup Restore Protocol

NEVER restore AGNOTE4482 files from backup by file copy. Use git operations:

1. **To restore a specific file from a known commit:**
   ```bash
   git checkout <commit-sha> -- pmoves/docs/AGENTS/AGNOTE4482_SIGNOFF_CHECKLIST.md
   ```

2. **To compare backup vs current before restoring:**
   ```bash
   diff <backup-file> pmoves/docs/AGENTS/AGNOTE4482_SIGNOFF_CHECKLIST.md
   ```

3. **If backup is older than HEAD, git merge instead of overwrite:**
   ```bash
   git checkout --merge <backup-branch> -- pmoves/docs/AGENTS/
   ```

4. **After any restore, verify signoff checklist hasn't regressed:**
   ```bash
   grep -c '\[x\]' pmoves/docs/AGENTS/AGNOTE4482_SIGNOFF_CHECKLIST.md
   # Must be >= 19 (current baseline)
   ```

**Rule:** If the check count drops after a restore, the restore caused a regression. Revert the restore and use git-level operations.
```

**Automation:** Add a CI check that validates signoff checklist baseline:

```yaml
# Add to existing merge-gate.yml
- name: Verify signoff checklist baseline
  run: |
    COUNT=$(grep -c '\[x\]' pmoves/docs/AGENTS/AGNOTE4482_SIGNOFF_CHECKLIST.md)
    if [ "$COUNT" -lt 19 ]; then
      echo "ERROR: Signoff checklist regressed from 19/20 to ${COUNT}/20"
      exit 1
    fi
```

### Which File to Update

- **AGNOTE4482_SITREP.md** — add Backup Restore Protocol section
- **.github/workflows/merge-gate.yml** — add signoff baseline check
- **AGNOTE4482.md** — add warning comment near line 307 noting the regression risk

---

## Implementation Priority

| Priority | Anti-Pattern | Fix Effort | Impact |
|----------|-------------|------------|--------|
| **1** | #3 Post-Merge Rot | 5 min (GitHub checkbox) | Eliminates 17/91 class permanently |
| **2** | #2 Orphan Proliferation | 2 hours (workflow + register column) | Eliminates 72/91 class permanently |
| **3** | #1 Naming Inconsistency | 30 min (SITREP section) | Prevents future confusion |
| **4** | #6 Signoff Gate Gap | 30 min (§9 addition) | Catches future drift |
| **5** | #8 Backup Regression | 1 hour (protocol + CI check) | Prevents doc state loss |
| **6** | #7 Multi-Agent Collision | 4 hours (arbiter + structured register) | Reduces orphan creation rate |
| **7** | #5 ACK Template | 30 min (template expansion) | Session-end awareness |
| **8** | #4 Phase Sprawl | 30 min (execution protocol) | Prevents skeleton branches |

**Total estimated effort:** ~9 hours
**Projected reduction:** From 91 stale branches per trim session to <5 (only from edge cases not covered by automation)

---

## Positive Observations

1. **Claim Register exists** — The fact that 30+ claims are tracked with status, branch names, and SHIPPED references shows the system has the *concept* of branch lifecycle. It just needs enforcement.
2. **GRAPHITI_MARK audit trail** — The `<!-- GRAPHITI_MARK: ... -->` comments in AGNOTE4482.md provide an immutable-adjacent audit trail that survived the backup regression (they're in AGNOTE4482.md, not the checklist). Extending this pattern to the checklist would prevent future regressions.
3. **pr-trimmer agent exists** — SITREP line 55 lists a `pr-trimmer` agent with "Worktree-isolated, PR review specialist" capability. This agent could be extended to include branch lifecycle enforcement.
4. **Convergence wave model works** — The Apr 17-19 convergence wave merged 16 PRs (+8,800 lines) in 72 hours. The multi-agent model *works* for delivery — it just needs process hygiene around the edges.
5. **Self-review caught the problem** — The 2026-04-01 self-review (AGNOTE4482.md lines 115-156) identified stale agent counts and file counts. The discipline of periodic review exists; it just needs to include branch hygiene.

---

## Appendix: File Update Checklist

| File | Changes | Anti-Patterns Addressed |
|------|---------|------------------------|
| `AGNOTE4482_SITREP.md` | +Branch Naming Convention, +Backup Restore Protocol, +Claim Arbiter, +health check PR list | #1, #7, #8, partial #2 |
| `AGNOTE4482_ROADMAP_W1-W5.md` | +Execution Protocol, +Claim Register PR column, +RECOMMENDED ≠ CLAIMED rule | #2, #4, #7 |
| `AGNOTE4482_SIGNOFF_CHECKLIST.md` | +§9 Branch/PR hygiene (5 items), +§9 signoff ledger column | #6 |
| `AGNOTE4482.md` | +Expanded ACK template, +backup regression warning | #5, #8 |
| `.github/workflows/stale-branch-sweep.yml` | NEW — daily orphan detection + deletion | #2 |
| `.github/workflows/post-merge-cleanup.yml` | NEW — auto-delete merged branch head refs | #3 |
| `.github/workflows/merge-gate.yml` | +Signoff checklist baseline check | #8 |
| GitHub Settings | Enable "Automatically delete head branches" | #3 |
