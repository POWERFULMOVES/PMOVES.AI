# Parent Branch PR Triage: `feature/launch-readiness-stage-0`

**Date:** 2026-05-18
**Author:** Z890-CLAUDE
**Operator:** DARKXSIDE (authorized splitting per 2026-05-18 "2 and or 3 this needs review")
**Branch:** `feature/launch-readiness-stage-0` (local-only, NOT on remote — `[gone]` per `git status -sb`)
**Status:** 24 commits ahead of `origin/main` (4 from 2026-05-18 z890-claude session + 20 historical from prior agents). Branch needs split into atomic, reviewable PRs OR a single mega-PR with clear commit boundaries.

---

## Why this exists

`feature/launch-readiness-stage-0` accumulated 20 commits from prior agent sessions (content-provenance pipeline, 5×5 credential audit, a2ui-renderer Pretext, CI hygiene, Stage 0 closure) plus 4 commits I added during the 2026-05-18 session (settings/dedup, bring-up docs, missing-linc ledger, Makefile alias + agnote CLAIM). The remote tracking branch was deleted — this work has never had a PR opened against main.

Per DARKXSIDE 2026-05-18: `feedback_atomic_commits_worktrees` says one concern per branch. 24 commits in one PR violates that. This doc proposes 7 PRs grouped by theme, with dependencies + risk tagged.

---

## Commit roll-up by theme

| # | Theme | Commits | Risk | Dependencies |
|---|---|---:|---|---|
| 1 | **Stage 0 launch docs** | 2 | Low (docs only) | None |
| 2 | **5×5 credential & naming-drift audit** | 1 | Medium (touches sign_trail.py + audit_naming_drift.py + 10 docs) | None |
| 3 | **Content provenance pipeline** | 5 | High (NATS subjects + JetStream + 3 services + contracts) | None — coherent feature |
| 4 | **a2ui-renderer Pretext + fixes** | 4 | Medium (CodeRabbit findings, Pretext engine) | None |
| 5 | **CI hygiene** | 2 | Low (workflow YAML fix + push trigger disable) | None |
| 6 | **AGNOTE board entry** | 1 | Low (docs) | None |
| 7 | **Z890 dual-NIC runbook + ops** | 6 | Low (4 docs + settings/compose dedup + missing-linc ledger) | Includes my 2026-05-18 session work |
| — | **Merge commits** | 3 | — | Replayed during rebase, dropped on cherry-pick |
| **Total** | | **24** | | |

---

## Detailed PR plan

### PR-A: Stage 0 launch docs (lowest-risk, ship first)

**Commits:**
- `3cd81a25 docs(launch): Stage 0 — initial layout validation for launch readiness`
- `745a28ef docs(launch): close Stage 0 — issue #1389 filed, all 5 nodes green`

**Scope:** Stage 0 layout validation docs + closure notes. Issue #1389 already filed.
**Risk:** Low — docs only.
**Branch name:** `docs/launch-stage-0-closure`
**Suggested reviewer lane:** CODEX-GPT5 (docs/prospectus) or operator.

---

### PR-B: 5×5 credential & naming-drift coherence gate

**Commits:**
- `d9f2c61e feat(audit): credential + naming-drift coherence gate (5×5 trail handshake)`

**Scope:** Per `HANDOFF_BRIEF_2026_05_09.md`, this is the Three-Body credential audit (claude-opus + z890-claude dual ACK). 1775 insertions, 11 files. Already signed off in prior session per the handoff brief — just needs PR opened.
**Risk:** Medium — touches `pmoves/tools/sign_trail.py`, `pmoves/scripts/audit_naming_drift.py`, `pmoves/config/signing_identity_cards.yaml`, 10 docs.
**Branch name:** `feat/credential-naming-drift-audit`
**Suggested reviewer lane:** operator + CODEX-GPT5 (docs lane). Already 10/10 tests passing per handoff brief.
**Status note:** This SHOULD have been a PR weeks ago. Prior session closed it as "technical delivery complete" but never opened the PR.

---

### PR-C: Content provenance pipeline (coherent feature, single PR)

**Commits (in order):**
- `500652d9 feat(content-provenance): contracts + SPARK working parity`
- `5153a0b1 feat(content-provenance): publishers — channel-monitor + ffmpeg-whisper emit content.raw.v1`
- `2f908a0b feat(content-provenance): consumers + content-provenance-gate worker + JetStream config`
- `53abcd45 feat(space-agent): NATS bridge — pmoves.space.action.v1 + pmoves.space.event.v1`
- `2eed4a79 feat(a2ui-renderer): Pretext text-layout engine + ProvenanceLivingDoc composition + /render/provenance route`

**Scope:** End-to-end content-provenance flow. Contracts → publishers → consumers → bridge → render. Per Z890-CLAUDE 2026-05-01 plan, this is "coherent content-provenance pipeline" worth preserving as a unit.
**Risk:** High — 5 services touched, 3 new NATS subjects (`pmoves.space.action.v1`, `pmoves.space.event.v1`, `content.raw.v1` + `content.hirag.accepted.v1`), JetStream config changes, new Pretext text-layout engine in a2ui-renderer.
**Branch name:** `feat/content-provenance-pipeline`
**Suggested reviewer lane:** 4090-CLAUDE (PR review/Shift Crew precedent) + SPARK (A2UI Remotion lane per 2026-05-18 attribution map) for the a2ui-renderer leg.
**Subdivision option:** Could split into "contracts + bridge" vs "publishers + consumers" vs "a2ui-renderer Pretext" if 5-commit PR is too large. Coherent reading argues against splitting.

---

### PR-D: a2ui-renderer CodeRabbit + Pretext follow-ups

**Commits:**
- `e20bee1c fix(a2ui-renderer): differentiate render:provenance:still vs :file scripts`
- `505ad032 fix(a2ui-renderer): make provenance helper source-backed and override-safe`
- `47db244e fix: address PR #1415 review findings (C1 H1 H2 H3 H4 M1 M3 M6)`
- `f2fb3493 fix: address CodeRabbit CRITICAL findings`

**Scope:** Post-Pretext CodeRabbit fixes + script differentiation. PR #1415 review findings (C1 H1 H2 H3 H4 M1 M3 M6 — 8 findings addressed).
**Risk:** Medium — a2ui-renderer is shared with SPARK lane (A2UI Remotion).
**Branch name:** `fix/a2ui-renderer-review-findings`
**Dependency:** Depends on PR-C landing first (Pretext engine ships in PR-C; these are fixes ON TOP of that).
**Suggested reviewer lane:** SPARK (A2UI owner) + 4090-CLAUDE (PR review lane).

---

### PR-E: CI hygiene

**Commits:**
- `3305033a fix(ci): suit-release-policy.yml YAML — bash continuation breaks block scalar`
- `ec1a49e3 chore(ci): disable self-hosted-builds.yml push + PR triggers`

**Scope:** Workflow YAML bug fix + intentional trigger disable (memory: `project_sitrep_2026_05_01` noted "self-hosted-builds triggers disabled" — that's this commit).
**Risk:** Low — workflow files only.
**Branch name:** `fix/ci-workflow-hygiene`
**Suggested reviewer lane:** operator (CI changes affect everyone).

---

### PR-F: AGNOTE board entry from prior session

**Commits:**
- `439c80b1 docs(agnote4482): board entry — Z890-CLAUDE sitrep + drift audit + handoff matrix`

**Scope:** AGNOTE4482PHI.t1.md board entry from Z890-CLAUDE 2026-05-01 sitrep + drift audit. Adds CLAIM + REVIEW + RELEASE entries the board has been missing.
**Risk:** Low — docs only.
**Branch name:** `docs/agnote-board-entry-2026-05-01-sitrep`
**Suggested reviewer lane:** operator. Could fold into PR-A as a docs bundle if reviewer prefers fewer PRs.

---

### PR-G: Z890 dual-NIC runbook + 2026-05-18 session ops

**Commits (in order):**
- `4a970a71 docs(ops): live fleet inventory + Z890 dual-NIC fix runbook (Phase 1)`
- `b3bc5f41 docs(ops): backlink Z890 runbook to cross-platform pattern doc`
- `88cac113 chore(ops): enable agent teams experimental + z890 compose dedup safe-path` (2026-05-18 session)
- `66561211 docs(ops): Windows-native bring-up roadmap + 2026-05-09 handoff cleanup + missing-linc skill scaffold` (2026-05-18 session)
- `9ab3242c docs(missing-linc): open findings ledger with 5 initial items` (2026-05-18 session)
- `711bc7e1 fix(Makefile) + chore(agnote): MLF-003 health-quick alias + 2026-05-18 lane CLAIM` (2026-05-18 session)

**Scope:** Z890 operations cluster — dual-NIC fix runbook + cross-platform backlink (pre-session) + experimental agent-teams settings + compose dedup safe-path + Windows-native bring-up roadmap + missing-linc findings ledger + Makefile health-quick alias + AGNOTE CLAIM (2026-05-18 session).
**Risk:** Low-Medium — settings.json env addition + compose dedup is structural; rest is docs.
**Branch name:** `feat/z890-ops-2026-05-18-session`
**Suggested reviewer lane:** operator (touches `.claude/settings.json`).
**Subdivision option:** Could split docs (4a970a71, b3bc5f41, 66561211, 9ab3242c) from settings/compose (88cac113, 711bc7e1) if reviewer wants tighter atomic boundaries.

---

## Dependency graph

```
PR-A (Stage 0 docs)             ──┐
PR-B (5×5 audit)                ──┤
PR-E (CI hygiene)               ──┼── all independent, can ship in any order
PR-F (AGNOTE board entry)       ──┤
PR-G (Z890 ops session)         ──┘

PR-C (content provenance) ── must ship before ── PR-D (a2ui-renderer fixes)
```

PR-C → PR-D is the only sequential dependency. The other 5 PRs can land in any order. SPARK + 4090 + operator can parallelize.

---

## Total PR overhead

- 7 PRs to open (-1 if PR-F folded into PR-A)
- 24 commits total reorganized
- 3 merge commits dropped on cherry-pick
- Estimated time per PR: ~10 minutes (branch + cherry-pick + push + PR description). Total: ~70 minutes by one agent, or ~20 minutes with 3 agents parallelizing.

---

## Alternative: single mega-PR

If reviewer overhead is the real bottleneck (vs. session capacity), the alternative is:
- **PR-mega:** Single branch with all 24 commits, well-organized commit messages, large but reviewable PR description that walks reviewers through the 7 commit clusters.
- Trade-off: faster to open, harder to revert individual concerns, atomic-merge violates `feedback_atomic_commits_worktrees`.

Default: do the split unless DARKXSIDE prefers mega.

---

## Recommended execution order (parallel, low-risk first)

1. **PR-A** (Stage 0 docs) + **PR-F** (AGNOTE board entry) + **PR-E** (CI hygiene) — ship these immediately, low review surface
2. **PR-G** (Z890 ops session) — operator review on settings.json change, otherwise low-risk
3. **PR-B** (5×5 audit) — already tested + dual-ACK'd, just needs PR for review
4. **PR-C** (content provenance pipeline) — biggest review, lands the most surface
5. **PR-D** (a2ui-renderer fixes) — after PR-C merges

Each PR's branch is cherry-picked off `origin/main` (fresh base), not off `feature/launch-readiness-stage-0` (which would inherit the others).

---

## Risks + open questions

- **Submodule pointer changes:** parent branch's working tree has 23 modified submodule pointer files (stashed under `z890-session-submodule-pointer-bumps-2026-05-18`). NONE of these should land in the 7 split PRs — they belong to a separate batch-promotion PR off main, per `pmoves-submodule-fleet` audit output (`SUBMODULE_FLEET_AUDIT_2026-05-18.md`).
- **DoX already promoted on main** (commit `90503552`, PR #1521) — any PR that touches the DoX gitlink will conflict on rebase. Verify before pushing each branch.
- **Cipher / transcribe-and-fetch upstream rewrites** still flagged from 2026-05-01 plan — any PR that touches these gitlinks needs upstream republish coordination first.
- **PR-C surface area** — 5 commits, content-provenance pipeline. If CodeRabbit + Codex + Kilo + 2 agent reviews fire, that's a lot of threads to drain. Consider letting only 1-2 reviewers touch it.

---

## Coordination

- This triage doc IS the handoff brief. Each PR's branch should reference this doc in its description.
- Lane attribution: most are Z890-CLAUDE's lane (this branch is mine), but PR-C's a2ui-renderer leg is SPARK's lane and PR-D is SPARK + 4090 review surface.
- Trail signing: each PR should sign via `/chit:sign-trail` at creation; trail IDs recorded in PR bodies per the established pattern (PR #1524, #1525).

ACK::Z890-CLAUDE::PARENT-BRANCH-PR-TRIAGE::2026-05-18
