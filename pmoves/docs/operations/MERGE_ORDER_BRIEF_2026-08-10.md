# Merge-order brief — 26 open PRs, 2026-08-10

**Author:** CLAUDE-OPUS-5 (4090) · **Scope:** order and dependency, verified against the tree. **Not** a recommendation about what should land — that is the operator's call. "Ready" below means *nothing blocks it mechanically*, not *it should merge*.

Every dependency here was checked by tree lookup (`git cat-file` / `git grep` against `origin/main` and the PR head). PR bodies were not treated as evidence.

> The queue is **26 open PRs**, not 13. It grew during the day.

---

## 1. Read before touching any red check

**`emit lifecycle trail` now fails on `pull_request` as well as `push`.** A red check on any PR means nothing until you open the failing job. Root cause, pinned:

The Archon commit our gitlink points at (`1e02907ac`) contains **seven nested gitlinks and no `.gitmodules` at all** — `external/PMOVES-Agent-Zero`, `external/PMOVES-BoTZ`, `external/PMOVES-Deep-Serch`, `external/PMOVES-HiRAG`, and three under `pmoves_multi_agent_pro_pack/`. Any recursive checkout dies at the first one:

```
fatal: No url found for submodule path 'PMOVES-Archon/external/PMOVES-Agent-Zero' in .gitmodules
```

This is a **PMOVES-Archon defect surfacing through our gitlink**, not a defect in our `.gitmodules`. Fix is one of: add `.gitmodules` inside PMOVES-Archon and bump our gitlink; drop the orphan gitlinks; or set the affected workflows to non-recursive submodules. Unowned as of this writing.

**Also:** merging anything currently needs an **admin override**. `required_approving_review_count: 1` plus the operator authoring every PR makes self-approval impossible.

Of 26 PRs: 15 clean, 7 `emit lifecycle trail` only, **2 with real failures**, 2 not applicable (see below).

---

## 2. Must not merge in current state

### #2524 — wrong base, by construction

**Base is `feat/dockerfile-copy-anchor`, not `main`.** Merging it as-is puts the a2ui-renderer fix on the #2521 branch, not on main. It is stacked deliberately: it deletes two entries from `pmoves/configs/dockerfiles/_known_copy_gaps.yaml`, and **that file does not exist on `main`** (verified: absent from `origin/main`). Landing it on main first would fail.

Required sequence: **#2521 → then retarget #2524 to `main` → then merge.** Or merge #2524 into the gate branch and land the pair as one.

### #2526 — red on the gate it introduces

Real failures on `merge-decision` and `python-tests`. The PR's stated purpose is to make `python-tests` capable of failing, so this may be the ratchet correctly catching pre-existing failures rather than a defect — but **that distinction has to be settled by its author before it lands**, because merging it red is what turns a required check into permanent noise. Not diagnosed here.

### #2517 — real failure

`check-suit-release-notes` fails. Cause not investigated; needs its author.

---

## 3. Verified hard dependencies

| Must land first | Then | Verified how |
|---|---|---|
| **#2521** (COPY gate) | **#2524** (a2ui fix) | `_known_copy_gaps.yaml` absent on `origin/main`; #2524 edits it |
| **#2514** (JuiceFS runbooks) | **#2515** (fleet handoffs) | `JUICEFS_MEDIA_MINIO_REFORMAT_RUNBOOK.md` absent on main; cited at `jetson-combiner-archon-assignment-2026-08-07.md:56` |
| **#2501** (JuiceFS cache bounds) | **#2502** (B850 + cross-node runbooks) | `pmoves/scripts/juicefs-cache-bounds.sh` absent on main; cited twice in `B850_BRINGBACK_RUNBOOK.md` (:162, :213) |
| **#2519** (defects from #2511) | any `branch-protection-sync` trigger work | #2519 adds the 5 missing `branch =` keys (`release`, `master`, `main`, `master`, `develop`). Without them the workflow's `branch="main"` fallback targets a branch that does not exist on 4 of those repos |

**One correction to the assumed #2502 → #2501 dependency.** It is narrower than stated. `juicefs-cross-node-setup.sh` **and** its make target already exist on `origin/main` (`pmoves/mk/egress.mk:318`). The only missing artifact is `juicefs-cache-bounds.sh`. So #2502 is dependent, but only on that one file — and the anchor ratchet would not flag it, since the cited make target resolves either way.

**No other hard dependencies found.** The remaining 18 PRs are independent of each other on the evidence available.

---

## 4. Collision map — files touched by more than one open PR

Seven files. Only the first is a hard conflict.

| File | PRs | Severity |
|---|---|---|
| **`pmoves/Makefile`** | **#2521, #2523, #2526** | **hard — overlapping hunks** |
| `pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md` | #2481, #2490, #2492, #2517 | append-only register; textual conflicts likely, semantically safe |
| `pmoves/configs/dockerfiles/_known_copy_gaps.yaml` | #2521, #2524 | resolved by the stacking above |
| `pmoves/configs/command_anchors/_known_gaps.yaml` | #2513, #2514 | both edit a ratchet baseline — second to land must re-run the ratchet, not hand-merge |
| `.gitmodules` | #2493, #2519 | different blocks (#2493 adds `PMOVES-nats-server`; #2519 edits the obico group) — likely clean, rebase second |
| `pmoves/docker-compose.yml` | #2468, #2501 | different services |
| `pmoves/docker-compose.arm64.override.yml` | #2446, #2468 | different services |

### The Makefile three-way

All three edit the same ~20 lines around the `validate-*` block:

```
#2521  @@ -1241,8 +1241,14 @@   and  @@ -1273,6 +1279,12 @@
#2523  @@ -1275,15 +1275,6 @@   (deletes 9 lines)
#2526  @@ -1270,6 +1270,17 @@
```

Whichever lands first forces a rebase of the other two. **#2523 is the one to land first** — it is a 9-line deletion of a duplicate with no dependants, so rebasing the other two onto it is trivial, whereas rebasing a deletion onto two insertions is not.

**`merge-gate.yml`:** among currently open PRs, **only #2526 touches it**. The expected inbound change from `trim-2511` is not an open PR yet; if it lands as a separate PR it will collide with #2526.

---

## 5. Merge order

Numbered where order is forced; grouped where it is not. **Parallel groups can go in any order, including simultaneously.**

**Forced sequences** (each arrow is a verified dependency):

1. `#2523` → `#2521` → `#2524` (retargeted to main) — Makefile deletion first so the gate rebases cleanly; gate before its first consumer.
2. `#2514` → `#2515`
3. `#2501` → `#2502`
4. `#2519` → (future branch-protection-sync trigger PR)

`#2526` slots after `#2521` and `#2523` for the Makefile, **and** after its own red checks are resolved.

**Independent — no ordering constraint, any time:**

`#2429` `#2446` `#2468` `#2481` `#2490` `#2492` `#2493` `#2496` `#2511` `#2513` `#2516` `#2518` `#2520` `#2522` `#2525` `#2527`

Two notes on that group:
- `#2513` and `#2514` both edit `_known_gaps.yaml`. Independent in content, but the **second to land must regenerate the baseline** rather than resolve the conflict by hand — a hand-merged ratchet baseline can silently re-accept a fixed defect.
- `#2493` and `#2519` both edit `.gitmodules`. Rebase whichever is second.

---

## 6. Blocked on an operator decision, not on another PR

| Item | Decision needed |
|---|---|
| `dockerfile:pr:2468` grant | Grant or decline |
| #2501 whitespace contract | Accept the proposed contract or specify a different one |
| `merge-gate` stub | Give it a body, or drop it from required checks. Right now it is a required check that cannot fail |
| Jacobian authors | Whether to report findings 1–2 upstream (their CI has not run their own checks since 2026-07-20). Not reported, per the read-only boundary |
| `persona.pmoves.ai` DNS | Traefik edge + DNS cutover. Blocks the whole LinkedIn content calendar in #2429 |
| Archon nested gitlinks | Which of the three fixes in §1 — this one is now costing a red check on every PR |

---

## 7. Known gap in the COPY gate (#2521), disclosed

`validate_dockerfile_paths.py` resolves `COPY` sources against compose `build:` contexts only — it globs `docker-compose*.yml` and nothing else. **`.github/workflows/integrations-ghcr.matrix.json` is a second, unscanned source of `(dockerfile, context)` pairs.**

This was not theoretical. #2524's Dockerfile fix would have broken the a2ui-renderer GHCR publish, because the matrix declared `context: pmoves/services/a2ui-renderer` while the fixed Dockerfile assumes the `pmoves` root. A follow-up commit (`8121e95cc`) on that branch corrects it. The gate did not and could not catch it.

The matrix has 15 entries; 3 declare a non-`pmoves` context for a Dockerfile under `pmoves/`. Whether any of those disagree with their Dockerfile is **not** audited here — extending the gate to read the matrix is the follow-up, and it is the fix that makes the audit unnecessary.

---

## Method

`gh pr list/view` for state and file sets; `git cat-file -e` and `git grep` against `origin/main` and each PR head for every dependency claim; `git diff --stat` and hunk headers for the collision map. Failing-check causes were read from the job logs, not inferred from the red badge. No PR was modified.
