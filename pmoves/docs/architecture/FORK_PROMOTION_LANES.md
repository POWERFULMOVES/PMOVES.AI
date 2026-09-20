# Fork Promotion — Lane Board

**Date:** 2026-09-20 · **Author:** 4090-claude
**Companion to:** [`DETERMINISTIC_HARDENING_RATCHET_RFC.md`](./DETERMINISTIC_HARDENING_RATCHET_RFC.md)

---

## Why this board exists

The hardening promotion stalled partway. Each fork was to be **promoted** — its
`PMOVES.AI-Edition-Hardened` branch carrying a real posture, its compose rebuilt
on the *forked* image rather than upstream's, and its images and compose
customised for PMOVES.AI production.

None of that completed. What is left is 41 repos carrying the name and nothing
behind it (measured: RFC §7.5), and a parent repo absorbing configuration that
belongs to the forks.

**The forcing function is quantified.** `POWERFULMOVES/PMOVES.AI` holds **90 of
its 100 Actions secrets** — 10 slots of headroom against a hard GitHub per-repo
limit. Devolving fork-specific secrets to the forks that own them is not
tidiness; it is the only road that does not end in a wall.

That reframes the work. Per-fork CI is not merely how hardening gets enforced —
it is the prerequisite for a fork to **hold its own secrets at all**, because a
secret is only useful where a workflow can read it.

## Dependency shape

```
Lane A (gate correctness)  ─── blocks ──▶ Lane D (promotion)
Lane E (branch topology)   ─── blocks ──▶ Lane D
Lane D (per-fork CI exists) ── enables ─▶ Lane C (secrets devolution)
Lane B (live root service) ─── independent, do now
Lane F (kiloclaw recovery) ─── independent, blocks Headscale/ScaleTail work
Lane G (prior-art salvage) ─── feeds Lane D
```

Lanes B and F are independent and should not queue behind the rest.

---

## Lane A — Gate correctness before distribution

**Status:** approved 2026-09-20 · **Owner:** 4090-claude · **Blocks:** Lane D

Distributing `hardening_ratchet.py` to 41 repos while it misclassifies correct
code would burn operator trust on first contact.

1. **Split the ledger.** `_known_gaps.yaml` is shrink-only — "removing an entry
   is the goal." A `kind: deliberate` entry describes an already-correct file
   that can never be removed, so mixing the two makes the target unreachable and
   the count stop meaning "remaining debt." Separate `known_gaps` (debt,
   shrink-only, `STALE` on fix) from `accepted` (correct-by-design, stable,
   reason required, never counted as debt).
2. **Teach the rule about runtime privilege drops.** `PMOVES-Archon`'s root
   `Dockerfile` ends `USER root` *deliberately*: its `ENTRYPOINT` fixes volume
   ownership as root then `exec`s via `gosu appuser`. Verified — the tool
   contains no reference to `gosu`, `su-exec`, `setpriv`, `tini`, `dumb-init`
   or `ENTRYPOINT`. Either detect the pattern or route it to `accepted`.
3. **First `accepted` entries.**
   - `PMOVES-Tailscale` (4/4 root) — **operator-confirmed intentional**:
     self-hosted, `tailscaled` needs elevated network capability. This is the
     first real test of the split.
   - `PMOVES-Archon` root `Dockerfile` — gosu drop, per (2).

**Done when:** a correct-by-design file is recorded as `accepted`, does not
appear in the debt count, and the debt count's goal state is reachable.

## Lane B — A live service is running as root

**Status:** open · **Priority:** highest real finding · **Independent**

`Pmoves-cipher`'s `Dockerfile.pmoves` declares **no `USER` directive** and runs
as root (`node:22-slim` default). It is the image backing the **live Cipher
memory service** and the most recently pushed repo in the survey (2026-09-18).
None of its 4 workflows reference hardening, USER checks, or image scanning.

Complications:
- It is one of the **5 forks with no fallback branch** (no `main`, no `master`),
  so a fail-closed gate would block its only branch.
- The parent repo's `_known_gaps.yaml` already carries a `not-deployed` entry
  for a *different* cipher Dockerfile under `pmoves/docs/`, with the reason
  "The running Cipher is the pmoves-cipher service, not this." That note is
  correct and points squarely at this lane: the real one was never covered.

**Do not wait for the RFC.** This is a one-line `USER` addition plus a rebuild.

## Lane C — Secrets devolution (the 90/100 driver)

**Status:** blocked on Lane D · **Owner:** unassigned

`PMOVES.AI` is at **90/100** Actions secrets. Every fork-specific credential
held in the parent is a slot the parent cannot use.

1. Inventory the 90 and classify: **parent-scoped** (fleet-wide, CI, GHCR,
   App keys) vs **fork-scoped** (belongs to exactly one fork's build or deploy).
2. For each fork-scoped secret, move it to the fork that owns it — possible
   only once that fork has a workflow able to read it (Lane D).
3. Record the mapping so the parent's count is auditable and cannot silently
   re-fill.

**Constraint:** secrets remain machine-emitted through the CHIT pipeline
(`bootstrap_env.py --rotate` → `chit-export` → `secrets-funnel`). Devolution
changes *where a secret lands*, never *how it is produced*, and manifests are
never hand-edited.

**Done when:** the parent's secret count is materially below 90 and each
remaining secret has a recorded reason to be parent-scoped.

## Lane D — Fork promotion and compose rebuild

**Status:** blocked on Lanes A + E · **Scale:** 26 forks with Dockerfiles

The original intent, unfinished: promote each fork, rebuild its compose on the
**forked** image rather than upstream's, and customise images and compose for
PMOVES.AI production.

Scope from the survey:
- **26 of 41** forks have Dockerfiles and are in scope.
- **15 of 41** have none — Lane D has no image work for them, though they may
  still hold fork-scoped secrets (Lane C) and still need branch repair (Lane E).
- **No fork anywhere runs a workflow enforcing the container-USER rule** —
  confirmed by grep across surveyed workflow YAML. Per-fork CI is being built
  from zero, not repaired.

Ring order (RFC §7.5.6): **ring 1 = `PMOVES-supabase`** — freshest merge, worst
measured posture among high-traffic repos (3/3 root, including app-serving
`studio` and `lite-studio`), 44 existing workflows so a new caller is not the
only thing running, and it exercises the `master`-only fallback path on the
first attempt rather than the fortieth.

Callers pin to a **tag**, never `@main` (RFC §5.2 #5), and promote 1 → 5 → 35.

## Lane E — Branch topology repair

**Status:** open · **Blocks:** Lane D fail-closed gating

**37% of the fleet breaks a literal `main` assumption.**

| State | Count | Consequence |
|---|---|---|
| `master` only, no `main` | 10 | tooling assuming `main` silently no-ops |
| **Neither `main` nor `master`** | **5** | no demotion target; a fail-closed gate blocks the only branch |

The five with no fallback: `Pmoves-cipher`, `PMOVES-neo4j`,
`PMOVES-space-agent`, `PMOVES-transcribe-and-fetch`, `Pmoves-hyperdimensions`.

Until repaired, Rule 4 runs **fail-open** on these. Blocking the only branch of
a repo converts a hardening gap into an outage.

Note `Pmoves-hyperdimensions` carries 29 `PMOVES.AI-Edition-Hardened-*`
per-component branch variants (`-A0`, `-Archon`, `-Cipher`, `-DoX`, …) and no
`main` — a branch-topology problem of its own shape.

## Lane F — kiloclaw recovery, mid-migration

**Status:** open · **Blocks:** Headscale + ScaleTail work · **Operator lane**

**Context that changes the shape of this lane:** kiloclaw was caught mid-flight
during a **split deploy, migrating to the KVMs and GPU hosts**. It is not a
steady-state host that fell over; it is a migration source that stopped
partway.

Two consequences:

- **Recover forward, not backward.** The goal is to complete the migration, not
  to restore the old box to service. The old box only needs to stay alive long
  enough to surrender its state.
- **The schema mismatch is explained by the migration.** A state DB at schema
  **17** under a build supporting **1** is what a split deploy produces when a
  newer build writes state on one side and an older build reads it on the
  other. It is a version-skew symptom of the migration, not independent
  corruption — so the fix is to converge OpenClaw versions across the split,
  not to repair the database.

All three KVMs are healthy and active (`pmoves-kvm2`, `pmoves-kvm4-1`,
`pmoves-kvm4-2`), so the migration targets are available.

Two distinct faults on the source box:

1. **Volume at 100%.** This is a *recurring* known failure with a safe playbook:
   orphaned `buildx_buildkit_builder-*_state` volumes, left because CI
   `docker buildx create` never calls `buildx rm`. On kvm4-1 in 2026-07 this was
   ~181GB across 40 volumes. Reclaim by exact pattern, **never**
   `docker volume prune`.
2. **OpenClaw state schema mismatch** — `/root/.openclaw/state/openclaw.sqlite`
   is at schema **17**; the running build supports **1**. A newer build wrote
   the DB and an older one is now running.

**Recovery order matters.** The workspace (`USER.md`, `SOUL.md`, `IDENTITY.md`,
`MEMORY.md`, `memory/`) is plain files and is **unaffected by the sqlite
mismatch**. Rescue it first, before any disk operation, so the rescue does not
depend on the cleanup succeeding. Then reclaim disk, then either restore the
newer OpenClaw build or sideline the sqlite and re-import the workspace.

**Work at risk:** `PMOVES-ScaleTail` has only a `main` branch and its recent
commits are all upstream PRs (#334–#338) — a fork-sync, not kiloclaw's work.
`PMOVES-Headscale` was last pushed 2026-06-22. **No kiloclaw work-in-progress
exists on either remote.** Anything in flight is local to the offline box.

The forward fix for (1) — pin one reusable buildx builder, scheduled
`buildx prune`, teardown `buildx rm` — was identified in 2026-07 and never
implemented, which is why this recurred.

## Lane G — Prior-art salvage

**Status:** open · **Feeds:** Lane D

`PMOVES-Open-Notebook` already carries unmerged branches named
`security/non-root-user`, `fix/phase-c-hardening`, `fix/phase-d-hardening`.
Someone scoped this exact work there and it never landed.

Before writing new hardening commits anywhere, check each fork's branch list for
existing attempts. Resurrecting a reviewed branch beats redoing it, and the
survey only inspected default branches — other forks may hold similar work.

## Not lanes

Kept visible so they are not silently absorbed:

- **`PMOVES-Headscale` is not hardened-default** — its default is `main`, and
  its registry reason reads "no PMOVES hardening layer identified." It is
  outside the 41 and should be triaged deliberately, not swept into Lane D.
- **`Pmoves-Health-wger`'s `demo/Dockerfile`** sets `USER wger` at line 102 then
  `USER root` at 133 — a genuine regression and exactly what last-USER-wins is
  built to catch. Ordinary debt, not an `accepted` case.
- **`PMOVES-BoTZ`** has 25 Dockerfiles, mostly under `archive/`. Sampled 5/12
  root-running is a **lower bound**. Triage archive-vs-live before counting it
  as debt.

## Related

- [`DETERMINISTIC_HARDENING_RATCHET_RFC.md`](./DETERMINISTIC_HARDENING_RATCHET_RFC.md) — design, constraints, full survey
- `pmoves/tools/hardening_ratchet.py` — Lane A edits this
- `pmoves/configs/hardening_ratchet/_known_gaps.yaml` — Lane A splits this
- `pmoves/configs/tac_schema.yaml` — Lane D's rollout is authored as a TAC tree
- PR #3119 — the RFC
