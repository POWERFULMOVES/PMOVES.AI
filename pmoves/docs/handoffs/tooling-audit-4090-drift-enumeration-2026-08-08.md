# Handoff — Ops/Tooling Drift Audit → 4090 (node affinity)

**Date:** 2026-08-08
**From:** z890-claude (infra lane, Delivery)
**To:** 4090-claude (minting/compose/fork/CI lane) — **named owner of this audit**
**Coordination:** Village Rule — CLAIM this lane in `AGNOTE4482PHI.t1.md` before starting item work.
**Related:** PR #2473 (buildx reclaim canonical, MERGED), PR #2479 (`_app-token` cross-job trap, MERGED),
`branch-protection-sync.yml:77-80` (documented auto-revoke pattern).

---

## Why 4090 owns this

4090 already has the tooling audit in flight and has **node affinity** for it: it runs Archon
(:3090), is deep in the compose/fork verification surface, and surfaced most of the drift findings
below. This handoff is **coordinate, not cold-assign** — z890's job was to (a) enumerate the
ops-script/make-target drift from the z890 side so the audit starts from a concrete list, and (b)
land the one immediate parity sub-fix (`docker-prune-all`, see item 1) so the leak is closed while
the broader unification is scoped.

**Division of labor (collision-free):**

| Lane | Owner | Items |
|------|-------|-------|
| Audit driver | **4090** | Items 1–5 below: unify cleanup impls, fix ci-expedition skill row, reconcile `claude-pmoves.sh`, consolidate `up-*` sprawl, document the submodule build-context gap |
| Drift enumeration (this doc) | z890 (done) | The concrete drift list below |
| Immediate parity sub-fix | z890 (done) | `docker-prune-all` `--all-inactive` backfill — branch `fix/docker-prune-all-buildx-reclaim` |

---

## 4090's in-flight findings (folded in, not re-derived)

Captured from 4090's paste so the audit has one surface:

- **Fork-completeness is uneven.** Archon / cipher / Open-Notebook carry Dockerfile + compose +
  examples; **Agent-Zero and surf are bare**; `mai-ui-agent` is a **PMOVES-authored shim** introduced
  in #2468 (not an upstream fork). Align the completeness bar or document the intended tiers.
- **Worktree/submodule build gap** (see item 5) — **7 sibling submodules / 8 services** with a
  sibling-context build can't build from a worktree because submodules aren't populated there.
  **Invisible in diffs** (CI checks out `submodules: recursive`). Runtime-topology property, not a
  code one.

  > **Correction (4090, at merge).** This bullet originally read "13 of 15". That figure
  > double-counted the same services re-declared across split overlays (agents 2 + apps 1 + media 3
  > + ui 1 = the same 7). Verified unique sibling-context builds in `pmoves/docker-compose.yml`:
  > `archon`, `cipher-api`, `pmoves-yt`, `openroom`, `llama-throughput-lab`, `transcribe-backend`,
  > `transcribe-frontend` — plus `docker-compose.n8n.yml`. Jellyfin is correctly excluded (local
  > build). The correction is also recorded at `AGNOTE4482PHI.t1.md:1787`; the stale headline is
  > left visible here rather than silently overwritten, because the audit owner needs to know which
  > number to stop chasing.
- **`_app-token.yml` cross-job auto-revoke trap** — fixed in #2479; the pattern is already documented
  in `branch-protection-sync.yml:77-80`. Sweep other workflows for the same shape.
- **ci-expedition skill error** — see item 2.

---

## Enumerated drift (priority order — hand to 4090)

### 1. Cleanup logic exists in 4 places, drifting

| Location | State |
|----------|-------|
| `pmoves/scripts/pmoves-disk-cleanup.sh` | **canonical** — has #2473 `buildx rm --all-inactive` fix |
| `deploy/provision/docker-fleet-cleanup.sh` | near-verbatim copy — has #2473 fix |
| `pmoves/mk/infra.mk` `docker-prune-all` | **was leaking** — only `docker builder prune`, never got the fix → **z890 backfilled** (branch `fix/docker-prune-all-buildx-reclaim`) |
| `.claude/skills/ci-expedition/SKILL.md` runner-hygiene block | 4th copy of the cleanup recipe |

**Target state:** collapse to one implementation; make targets + the skill *reference* it rather
than re-embed it. The z890 sub-fix restored parity across the three executable copies as a stopgap;
the unification is 4090's call (a shared script the make target and skill both invoke).

### 2. ci-expedition skill error (`SKILL.md:29`)

The row claims `pull_request_review` resolves the workflow from the **default branch**. Wrong —
`pull_request_review` (like `pull_request`) resolves the workflow from the **PR head/base ref**, not
default. Proven via #2479 / #2475. `issue_comment` and `push` *do* resolve from default; the row
conflates them. The wrong row misdirects the next `startup_failure` triage.

- Correct the canonical `.claude/skills/ci-expedition/SKILL.md`.
- **Also duplicated into 4 `.claude/worktrees/agent-*` copies** → reconcile those copies too.

### 3. Two divergent `claude-pmoves.sh`

- `deploy/provision/claude-pmoves.sh` (6523 B)
- `pmoves/scripts/claude-pmoves.sh` (642 B)

Pick the authoritative one; make the other a thin reference or delete. **Crush setup is similarly
split** across `deploy/provision/` and `pmoves/scripts/` — same reconcile.

### 4. `up-*` target sprawl (89 targets)

> **Caveat (4090, at merge) — measure call sites before calling anything superseded.**
> These are *inventory* candidates, **not** a retire list. The `up-core-*` family is a
> dependency chain, not three siblings: `up-core-gpu` invokes `up-core-capable`
> (`pmoves/Makefile:2567`), which invokes `up-core-hardened` (`:2562`). Retiring
> `up-core-hardened` as "superseded" would break the canonical capable **and** GPU
> bring-up roads. A textual reference count is not evidence of disuse — the first pass at
> this list scored `up-core-hardened` at zero references precisely because the grep
> excluded makefiles to skip *definitions*, and thereby excluded *call sites* too.
> Same shape for `up-cipher-nobuild`, which is the existing workaround for item 5's build
> gap and is a keeper regardless of reference count. Deliverable is an inventory; the
> operator picks what dies.

Inventory candidates by family:
- `up-agents-{published,ui,stack,hardened,standalone,auto,integrations}`
- `up-core-{hardened,capable,gpu}`
- `up-all` vs `up-all-new`
- `up-cipher-{nobuild,full}`
- `secrets-funnel*` (4 near-siblings)

### 5. Sibling-submodule build gap (runtime-topology finding)

7 services build from `../PMOVES-<X>` sibling paths that aren't populated inside a worktree:
`archon` (:3132), `cipher-api` (:3265), `pmoves-yt` (:2274), `openroom` (:3371), `transcribe-*`,
`llama-throughput-lab`, `tokenism-ui` (nested `./`) — **plus `n8n`** (in `docker-compose.n8n.yml`).
**Exclude `jellyfin`** (local build). Same contexts are re-declared across split overlays.
`up-cipher-nobuild` is the existing workaround.

**Target:** document + make CI/worktree-aware. This needs a **runbook/check**, not a code review —
CI is blind to it because it checks out `submodules: recursive`.

---

## Note for the reviewer

The worktree/submodule gap (item 5) is invisible in a diff. It's a runtime-topology property, so it
needs a runbook or a preflight check, not a line-by-line code review.

---

## Also folded in (skill hygiene)

- `archon.crawl.*` retirement — **operator wiring decision, parked** (speculative contract neither
  project implemented; publish→echo circuit, no fetch). Not built against yet. Not part of this audit
  unless the operator decides to retire vs let a VL service define its own contract.
