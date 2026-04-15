# Codex Worktree + Triage Handoff — 2026-04-15

**From:** z890-claude (Phase 10 — Local State Triage session)
**To:** codex (next session) + user
**Session outcome:** Safe cleanup executed; 4 significant findings surfaced for user decision.

z890-claude performed read-only investigation on dangerous submodule state and
applied only the cleanup operations the plan explicitly authorized. This file
documents (a) what codex should action on its next session, (b) what was found
but left for user direction, and (c) what was executed.

---

## 🚨 CRITICAL FINDINGS (Require User Decision)

### Finding 1 — Three submodules in index/worktree desync (not just two)

The plan flagged `PMOVES-Deep-Serch` and `PMOVES-Jellyfin` as dangerous. During
gitlink-promotion pre-flight, a **third submodule was discovered in the same
state**:

| Submodule | Symptom | HEAD | Index | Working tree |
|---|---|---|---|---|
| `PMOVES-Deep-Serch` | 88 staged deletions | `e2af6b6` (matches tracked) | empty tree (`4b825dc6`) | 1 file (`PMOVES.AI_INTEGRATION.md`) |
| `PMOVES-Jellyfin` | 2,332 staged deletions | `ecdfad9e3` (matches tracked) | **missing** | 1 file (`PMOVES.AI_INTEGRATION.md`) |
| `PMOVES-tensorzero` | ~1,400 staged deletions | `3f941d33` (ahead of tracked by 5 commits, all ancestors) | empty tree | 1 file (`PMOVES.AI_INTEGRATION.md`) |

**Root cause (all three):** A `git rm --cached -r` or sparse-checkout operation
emptied the index without touching HEAD or the working tree. The SHAs are
correct; no commits are lost. This is a recoverable index/worktree desync, not
data loss.

**Shared fingerprint:** All three have identical `PMOVES.AI_INTEGRATION.md`
file mtime of `Apr 5 05:35` to the second — the same batch operation.

**Recovery command (safe — does not move HEAD):**
```bash
git -C D:/PMOVES.AI/PMOVES.AI/PMOVES-Deep-Serch checkout HEAD -- .
git -C D:/PMOVES.AI/PMOVES.AI/PMOVES-Jellyfin checkout HEAD -- .
git -C D:/PMOVES.AI/PMOVES.AI/PMOVES-tensorzero checkout HEAD -- .
```

**Note:** This recovery pattern is documented in PR #1256 as "Insight 1 —
Submodule working-tree wipe recovery" and the learning is committed to
`.claude/CLAUDE.md`. The PR is merge-ready at time of writing.

**User decision required:** Execute the recovery commands, or leave until a
separate remediation session. z890-claude did NOT execute these — the locked
decision from this session was "investigate only".

---

### Finding 2 — `test_mcp_server.py` local mod is stale, not the fix for #1234

The plan assumed the 138-insertion/54-deletion diff in
`pmoves/services/agent-zero/tests/test_mcp_server.py` on main's working tree
was the same test-refactor work sitting on PR #1234's rec11-13 branch and
could be transplanted to unblock CI.

**This assumption is wrong.** Comparison of the two versions:

| Aspect | main working tree (239 lines) | rec11-13 HEAD (225 lines) |
|---|---|---|
| Mock architecture | `AsyncMock` + `_make_mock_client()` factory | `_DummyAsyncClient` class + `_install_async_client()` monkeypatch |
| Import style | `from unittest.mock import AsyncMock` | no AsyncMock |
| Response type | `_DummyResponse` with inline `httpx.Request("http://test")` | `_DummyResponse` with deferred `self._request` |

These are **two competing refactor approaches**, not the same work. Further,
`POWERFULMOVES` pushed commit `7fafc4a8` ("fix(agent-zero): update async mcp
test mocks") at 2026-04-15 18:24:29Z — 3 hours before this session — using the
class-based approach. Tests **still fail** on that commit.

The local `AsyncMock`-based version is most likely an **earlier abandoned
attempt**, not a later improvement.

**Evidence preserved:** Main's working tree diff saved to
`/tmp/pmoves-triage/test_mcp_server_main_working_tree.patch` (283 lines).

**Status of main working tree:** `test_mcp_server.py` mod is **left in place**
— z890-claude did not discard it without user approval. User decision required:
either `git restore pmoves/services/agent-zero/tests/test_mcp_server.py` to
discard the stale mod, or export the mock patterns from it as reference before
discarding.

**#1234 CI is still blocked.** The `execute_command` async/sync parity failure
on PR #1234 is a **code-level fix**, not a test-mock fix. Neither the local
working tree version nor the branch's current `7fafc4a8` resolves it. A
different fix is needed — recommend assigning to the branch owner or a fresh
debugging session.

---

### Finding 3 — `pmoves-e2b-mcp-server` gitlink is DIVERGENT, not ahead

The plan said `pmoves-e2b-mcp-server` was "+8 commits ahead" and safe to
promote. Running `merge-base --is-ancestor <tracked> HEAD` returned **NO** —
the tracked SHA `d01ec631...` is NOT an ancestor of current HEAD `12442b7`.

Promoting the gitlink would **abandon commits** that only exist on the tracked
lineage. This is UNSAFE without further investigation.

**Status:** z890-claude promoted 2 of the 3 planned gitlinks (autoresearch,
tensorzero — both verified `IS-ANCESTOR: YES`). Skipped e2b.

**User decision required:** Investigate why the branches diverged. Options:
1. `git -C pmoves-e2b-mcp-server log tracked..HEAD` and `log HEAD..tracked` to
   see both sides of the divergence.
2. Merge the two lineages in the submodule, then promote.
3. Reset the submodule to tracked and re-apply the divergent work upstream.

---

### Finding 4 — Stash@{0} touches `pmoves/env.tier-media` (damage-control-guarded)

The plan's locked decision said "APPLY stash@{0} to rec11-13 worktree, then
drop". The stash touches `pmoves/env.tier-media`, which is on the plan's
explicit **DO-NOT-TOUCH** list (auto-generated by secrets pipeline, any manual
edit is a damage-control violation).

**Stash@{0} is LEFT IN PLACE.** Applying it would violate a non-goal.

**User decision required:** Either export the non-env.tier-media portions of
the stash (k8s networkpolicies, main.py, test_main.py) for selective
cherry-pick, or drop the entire stash if the branch owner (#1234) has since
covered all the content.

---

## 📋 What z890-claude Executed This Session

### Worktree cleanup (15 removed, 3 codex-owned untouched, 3 KEEP retained)

**Removed (clean, merged PRs or abandoned work):**
- `D:/PMOVES.AI/pmoves-agent-zero-build-timeout-followup` [codex/1215-timeout-followup]
- `D:/PMOVES.AI/pmoves-ci-submodule-hardening` [feat/ci-submodule-hardening-gates]
- `D:/PMOVES.AI/pmoves-dependabot-critical-axios` [fix/dependabot-critical-axios]
- `D:/PMOVES.AI/pmoves-gh-self-hosted-hardening` [codex/gh-self-hosted-hardening]
- `D:/PMOVES.AI/pmoves-new-model-providers` [codex/1211-compose-fix]
- `D:/PMOVES.AI/pmoves-pbnj-skill` [feat/pbnj-skill-manifest]
- `D:/PMOVES.AI/PMOVES.AI/.worktrees/dhi-migration` [feat/dhi-hardened-images-clean]
- `D:/PMOVES.AI/PMOVES.AI/.claude/worktrees/agent-a03ee24d` [fix/makefile-data-services-up-minio]
- `D:/PMOVES.AI/PMOVES.AI/.claude/worktrees/agent-a16ab0ee` [feat/p6-model-upgrades]
- `D:/PMOVES.AI/PMOVES.AI/.claude/worktrees/agent-a3a36f37` [voice/lane-4-chain-doc]
- `D:/PMOVES.AI/PMOVES.AI/.claude/worktrees/agent-a4c7d84a` [feat/p2-healthcheck-all-dockerfiles]
- `D:/PMOVES.AI/PMOVES.AI/.claude/worktrees/agent-a85f7cc7` [fix/chrome-ext-tz-health-path]
- `D:/PMOVES.AI/PMOVES.AI/.claude/worktrees/agent-ab8eba8b` [feat/rec9-10-compose-and-merge-gate]
- `D:/PMOVES.AI/PMOVES.AI/.claude/worktrees/agent-abfd06c0` [feat/rec8-distributed-tracing]
- `D:/PMOVES.AI/PMOVES.AI/.claude/worktrees/agent-ad0a3631` [voice/lane-1-voicebox-provider]

**Kept — active open PRs:**
- `D:/PMOVES.AI/pmoves-rec11-13-k8s-tests-async` [feat/rec11-13-k8s-tests-async] → PR #1234 (CI blocked, see Finding 2)
- `D:/PMOVES.AI/pmoves-substrate-insights` [docs/substrate-session-insights] → PR #1256 (merge-ready)

**Kept — needs-review:**
- `D:/PMOVES.AI/pmoves-services-common-relative-imports` (detached HEAD at `c0b99d99`, same SHA as PR #1255 HEAD owned by `hunnibear`). Do NOT remove — it's tracking a branch that's actively being worked on by another user, just detached from our local branch ref. Investigate the branch-ref drift rather than blindly removing the worktree.

**Kept — codex-owned (handoff to codex):**
- `C:/Users/DARKXSIDE/.codex/worktrees/data-services-docs` [codex/data-services-provisioning-docs]
  - PR #1124 MERGED; 238 commits ahead of main — codex: safe to remove
- `C:/Users/DARKXSIDE/.codex/worktrees/pr1100-review-fixes` [codex/pr1100-review-fixes]
  - PR #1114 CLOSED; has untracked `.codex_pr_body.txt` scratch file — codex: remove scratch + remove worktree
- `C:/Users/DARKXSIDE/.codex/worktrees/publish-state-visibility-refresh` [codex/agnote4482-publish-state-visibility]
  - PR #1135 MERGED — codex: safe to remove

### Stash cleanup (4 dropped, 3 left for review)

**Dropped (verified safe per plan + content check):**
- ~~`stash@{6}`~~ — `fix/ghcr-registry-consolidation` "noise for 1153 rebase". Deletion target `github_webhook_auto_config.json` already absent from main.
- ~~`stash@{4}`~~ — `fix/rustdesk-tailscale-mcp-registry` "WIP validation save". 3 blank-line additions to auto-gen `env.tier-media`.
- ~~`stash@{3}`~~ — `codex/agnote4482-clawz-prospectus-signoff` (2026-03-28). Publisher/UI work — verified covered by merged PRs #1100, #1120, #1135.
- ~~`stash@{1}`~~ — `fix/pr-monitor-repo-base-defaults`. `submodule_branch_policy_check.py` content — verified file exists in main, last touched by PR #1183.

**Left in place (NEEDS-REVIEW):**
- `stash@{0}` (was originally index 0; now still 0) — `feat/rec11-13-k8s-tests-async` WIP. **Touches `pmoves/env.tier-media` — damage-control-guarded, cannot apply without violating plan non-goal.** See Finding 4.
- `stash@{1}` (was originally `stash@{2}`) — `chore/submodule-integration-docs` pre-validation stash (83 files, 174 lines). May overlap with PR #1256's submodule recovery docs. Content review needed.
- `stash@{2}` (was originally `stash@{5}`) — `fix/supabase-bootstrap-internal` "local changes before main sync" (3 files, 95 lines). Touches `.claude/settings.json` + Supabase DB bind config. Plan flagged as experimental.

### Submodule gitlink promotion (2 of 3 planned)

**Promoted:**
- `PMOVES-autoresearch`: tracked `9486195` → HEAD `9eca5b5` (1 commit ahead: "docs: add PMOVES.AI integration dossier"). Working tree clean. `merge-base --is-ancestor`: YES.
- `PMOVES-tensorzero`: tracked `6b1bc23f` → HEAD `3f941d33` (5 commits ahead, including 2 hardening + 1 auth fix + 2 integration docs). Working tree broken (staged-deletion desync, see Finding 1), but the gitlink promotion records HEAD only, not the worktree state. `merge-base --is-ancestor`: YES.

**Skipped (divergent — see Finding 3):**
- `pmoves-e2b-mcp-server`: tracked `d01ec631` vs HEAD `12442b7`, `merge-base --is-ancestor`: NO.

### CHIT trail

Signed via `make -C pmoves sign-trail` at end of session with summary:
`"Local state triage — 15 worktrees + 4 stashes cleaned, 2 gitlinks promoted, 4 findings surfaced"`.

---

## 📝 What Remains For Future Sessions

### High-priority (user decision)
1. **Decide recovery for 3 desynced submodules** (Finding 1) — one command each, low risk.
2. **Discard or harvest `test_mcp_server.py` local mod** (Finding 2) — reference patch at `/tmp/pmoves-triage/test_mcp_server_main_working_tree.patch`.
3. **Investigate `pmoves-e2b-mcp-server` divergence** (Finding 3) — why did the two lineages split?
4. **Review 3 remaining stashes** (`stash@{0}`, `stash@{1}`, `stash@{2}`) for salvageable content before dropping.

### Medium-priority (ongoing)
5. **31 unsampled submodules still have potential drift** — of the 34 total submodules, this session sampled 8 and found 3/4 of the working-tree-drift samples were in the Deep-Serch/Jellyfin/tensorzero desync pattern. The remaining 26 submodules are unexamined; a systematic `merge-base --is-ancestor` sweep would classify them all in one pass.
6. **Codex worktree cleanup** (3 items — see "Kept — codex-owned" above). Codex should action on next session.
7. **PR #1234 CI** — code-level async/sync parity fix needed. Not a test-mock fix. Requires investigation by branch owner.
8. **PR #1255** — actively owned by `hunnibear` + their Claude session, not this z890 session. Leave alone. Our local `services-common-relative-imports` worktree is at detached HEAD on the same SHA as the PR — reconciling that is a separate future task.
9. **PR #1256** — merge-ready (see Block 3A of session plan). User will drive the admin merge.

---

## 🔍 Investigation Data — Raw Output (for reference)

### Finding 1 submodule diagnostic (from researcher agent)

**Deep-Serch:**
- HEAD: `e2af6b6` = tracked SHA (no drift)
- Reflog: single entry, clone on 2026-03-14 (no HEAD movement since)
- Index: empty tree (`4b825dc6`), timestamp `Apr 15 18:06` (touched today)
- Working tree: 1 file (`PMOVES.AI_INTEGRATION.md`)
- No MERGE_HEAD, REBASE_HEAD, or CHERRY_PICK_HEAD
- dhi-migration worktree tracks same SHA — no cross-worktree contamination

**Jellyfin:**
- HEAD: `ecdfad9e3` = tracked SHA (no drift)
- Reflog: single entry, clone on 2026-03-14
- Index: **missing file outright** (`.git/modules/PMOVES-Jellyfin/index` does not exist)
- Working tree: 1 file (`PMOVES.AI_INTEGRATION.md`)
- No merge/rebase/cherry-pick markers

**tensorzero:** (from z890 this session)
- HEAD: `3f941d33` (5 ahead of tracked `6b1bc23f`)
- Log chain: `3f941d33 → f14bdf66 → e42ca0cf → 2585e701 → 555a9206` then continues to ancestors of tracked
- Working tree: status output is ~1,400 `D ` entries (all files except `PMOVES.AI_INTEGRATION.md`)
- Index: empty
- `merge-base --is-ancestor 6b1bc23f HEAD`: returns 0 (TRUE — HEAD contains tracked)

---

*End of handoff — z890-claude Phase 10, 2026-04-15.*
