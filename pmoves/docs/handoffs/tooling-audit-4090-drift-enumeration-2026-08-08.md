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

> **Status (4090, at merge) — the table above is HISTORICAL, the leak is closed.**
> Two of the four already carried the #2473 fix when this was written
> (`pmoves/scripts/pmoves-disk-cleanup.sh`, `deploy/provision/docker-fleet-cleanup.sh`).
> `pmoves/mk/infra.mk` was fixed by z890 in **#2480**, and the
> `.claude/skills/ci-expedition/SKILL.md` copy shipped with item 2. **Current leak count: 0.**
> What remains is *de-duplication*, not remediation — do not re-audit for a live leak.

**Target state:** collapse to one implementation; make targets + the skill *reference* it rather
than re-embed it. All four are now at parity, so the unification is a maintainability change with
no outstanding leak behind it.

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

**Keep both entry points — they are not duplicates.** `deploy/provision/claude-pmoves.sh` loads
`env.shared` and the MCP roster; `pmoves/scripts/claude-pmoves.sh` provides positional-agent
selection. Make the smaller a thin **delegate** to the larger while preserving positional-agent
selection and MCP credential loading. **Do not delete either** — each carries a capability the
other lacks, so a straight pick loses function. **Crush setup is similarly split** across
`deploy/provision/` and `pmoves/scripts/` — same reconcile, same caution.

### 4. `up-*` target sprawl (89 definitions, 88 unique names)

> **Both counts are correct and the gap is a finding.** `grep -c '^up-[a-z0-9-]*:'` over
> `pmoves/Makefile` (82) + `mk/egress.mk` (1) + `mk/infra.mk` (3) + `mk/yt-cookies.mk` (3) = **89
> definitions**; `sort -u` gives **88 names**. The difference is **`up-openroom`, defined twice in
> `pmoves/Makefile` (:1279 and :1335)** — byte-identical recipes, so behaviour is unaffected, but
> make emits an overriding-recipe warning and the second definition wins. Deleting one is the
> single safest item on this list.

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

**7 sibling-context services / 8 total** build from `../PMOVES-<X>` paths that aren't populated
inside a worktree — the same list verified at the top of this document, restated here so the two
sections cannot drift apart:

`archon`, `cipher-api`, `pmoves-yt`, `openroom`, `llama-throughput-lab`, `transcribe-backend`,
`transcribe-frontend` — **plus `n8n`** (in `docker-compose.n8n.yml`), for **8 services**.

`tokenism-ui` was listed here in the original enumeration and is **removed**: its context is a
nested `./`, not a sibling submodule path, so it builds fine from a worktree. **Exclude
`jellyfin`** (local build). The same contexts are re-declared across split overlays, which is what
produced the original "13 of 15". `up-cipher-nobuild` is the existing workaround.

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
