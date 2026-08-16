# Mesh Stage A — per-artifact mechanism decisions

**Date:** 2026-08-16
**Author:** 4090-CLAUDE (field)
**Status:** Decision surface. **Nothing here is executed.** Every row needs an operator choice.
**Parent:** [`mesh-live-collaboration-layer-plan-2026-08-08.md`](./mesh-live-collaboration-layer-plan-2026-08-08.md) (PR #2481)

---

## Why this document exists

The mesh plan blocks its own Stage A:

> **Mechanism — OPEN DECISION, must be settled per artifact before Stage A is executable.**
> `git-lfs pointer` and `remove-from-tree + mesh path` are not interchangeable […] **Stage A
> cannot start until each row of the table above names one of the two, plus its bootstrap and
> restore path.**

The plan's table has five rows, three of which mix a measured size, a file count, and one
explicitly-unconfirmed estimate. This document re-measures the whole surface and lays out the
decision per category, so the block can be lifted by choosing rather than by re-auditing.

**Measured against `origin/main` @ `017de5369` on 2026-08-16** with:

```bash
git ls-tree -r -l HEAD | awk '$4 > 1048576 {print $4, $5}' | sort -rn
```

Tracked files in this repository only. Submodule contents are out of scope — separate repos,
separate hygiene.

---

## What is actually there

**75 tracked blobs over 1 MiB, totalling 259.1 MB.** The plan names two directories accounting
for 224 MB of that; the remaining ~35 MB appears in no row of the plan, including the single
largest file in the repository.

By file type:

| Type | Size | Files |
|---|---:|---:|
| `.wav` | 70.8 MB | 1 |
| `.opus` | 50.3 MB | 30 |
| `.pdf` | 48.1 MB | 11 |
| `.mp3` | 27.0 MB | 6 |
| `.txt` | 23.5 MB | 5 |
| `.png` | 14.9 MB | 10 |
| `.m4a` | 13.1 MB | 6 |
| `.html` `.docx` `.ipynb` `.vtt` `.js` | 11.4 MB | 6 |

By area:

| Area | Size | Files >1 MiB |
|---|---:|---:|
| `CATACLYSM_STUDIOS_INC/` | 116.8 MB | 10 |
| `pmoves/data/` | 70.2 MB | 40 |
| `pmoves/docs/` | 50.2 MB | 14 |
| everything else | 21.9 MB | 11 |

### The plan's figures, re-checked

| Plan says | Measured today | Verdict |
|---|---|---|
| beats `98 MB` | **98 MB** | holds |
| CATACLYSM `125 MB` | **126 MB** | holds |
| evidence `38 PNGs`, "~180 not confirmed" | **180 files, 16.9 MB, of which 38 are PNG** | **both numbers were right.** The plan read ~180 as a PNG estimate and could not confirm it; 180 is the total file count in `pmoves/docs/evidence/`, 38 is the PNG subset. The uncertainty it flagged is resolved. |

---

## Three findings that change Stage A's shape

**1. 17.0 MB (7%) is exact duplication — needs no mechanism at all.** Two blobs are byte-identical
at two paths each:

| Size | Paths |
|---:|---|
| 9.2 MB | `pmoves/docs/PMOVESCHIT/main.pdf` · `pmoves/docs/context/main.pdf` |
| 7.8 MB | `pmoves/docs/PMOVES.AI PLANS/stocksharp-stocksharp.txt` · `pmoves/docs/repoingest/stocksharp-stocksharp.txt` |

Neither LFS nor the mesh is involved: one of each pair is redundant. This is the cheapest 17 MB
on the list and it should be resolved *before* any mechanism decision, because it changes the
totals every other row is weighed against.

**2. The two largest files are one recording in two encodings — 89.2 MB for a single asset.**

```
70.8 MB  CATACLYSM_STUDIOS_INC/evidence/Hybrid Utility Tokens_ Stable, Scalable, and Compliant.wav
18.4 MB  CATACLYSM_STUDIOS_INC/evidence/Hybrid Utility Tokens_ Stable, Scalable, and Compliant.mp3
```

Different blobs, so the dedup pass above does not catch them. This is **34% of the entire
large-file surface in one asset**, and it is the largest single decision on the list — but the
decision is "which encoding is the artifact of record", not "LFS or mesh". A lossless master
kept for archival is a legitimate answer; keeping both in git is not obviously one.

**3. The plan's table under-scopes the job.** `pmoves/docs/` carries 50.2 MB across 14 large
files — PDFs and repo-ingest text dumps — and appears in the plan only as the evidence-PNG row.
Scope Stage A from the command, not from the table.

---

## The decision, per category

The two mechanisms are not interchangeable, and the difference is operational:

- **LFS pointer** — the path stays resolvable in every clone and CI job, at the cost of an LFS
  dependency in every clone and CI job. Bandwidth is metered on GitHub-hosted LFS.
- **Remove-from-tree + mesh path** — the artifact becomes unavailable to any node that cannot
  reach the mesh, including CI runners and any offline checkout. Rollback means re-adding bytes.

| # | Category | Bytes it removes | Recommended | Why, and what it costs |
|---|---|---:|---|---|
| 1 | Exact-duplicate blobs (2 pairs) | **17.0 MB** | **Delete the redundant copy** | No mechanism needed. Do this **first** — it changes the byte count of rows 4a and 5 below. Requires naming which path is canonical. |
| 2 | `CATACLYSM_STUDIOS_INC/evidence/*.wav` master | **70.8 MB** | **Remove-from-tree → mesh `/business`** | A lossless master is archival, not working material; nothing in the repo reads it. Largest single reclaim on the list. **Gate:** mesh path confirmed live and retained first. |
| 3 | `pmoves/data/beats/**` audio (41 files) | 98 MB | **LFS, not remove** | The plan itself requires beats to keep serving `/media/beats` for the voice pipeline. Until that path is *verified live*, removing from the tree risks a working pipeline. LFS gets the bytes out of a clone while keeping the path resolvable. **I could not verify the mesh path from this node — do not treat it as confirmed.** Excluded from the net below for that reason. |
| 4a | `pmoves/docs/**` PDFs, post-dedup (3 files) | **12.7 MB** | **Remove-from-tree → mesh `/docs`** | Rendered output, not source. `PMOVESCHIT/main.pdf` 9.2 MB is already accounted for in row 1. |
| 4b | `CATACLYSM_STUDIOS_INC/**` PDFs (7 files) | **26.3 MB** | **Remove-from-tree → mesh `/business`** | Rendered decks. The plan's split principle keeps the `.csv`/`.md` source in git. |
| 5 | `repoingest/*.txt` dumps, post-dedup (4 files) | **15.7 MB** | **Delete outright — do not move** | These are *generated ingests of other repositories* — neither source nor artifact, but a cache. Moving a cache to the mesh preserves something that should be regenerable. Confirm the generator is tracked before deleting. |
| 6 | `pmoves/docs/evidence/**` (180 files) | 16.9 MB | **Leave in git** | 94 KB average. The clone-hygiene argument is weak at this size, and evidence screenshots earn their keep by being linkable from a commit. Revisit if it grows. |
| 7 | `.minimax/`, `research/`, `website/` | ~7 MB | **Leave in git** | Below the threshold where either mechanism pays for its own complexity. |

**Net if rows 1, 2, 4a, 4b and 5 are taken — 142.5 MB out of the working tree**, of which
**32.7 MB is deleted** (rows 1 and 5) and **109.8 MB moves to the mesh** (rows 2, 4a, 4b).
Beats (row 3) is deliberately excluded until its mesh path is validated.

> The per-row byte figures are **post-dedup and non-overlapping**. An earlier draft of this
> table summed category totals instead and double-counted the duplicate pairs across rows 1, 4
> and 5 — inflating the net by ~17 MB and misattributing 26.3 MB of CATACLYSM PDFs to
> `pmoves/docs/`. If you re-derive these numbers, derive them per path, not per file type.

---

## What still has to be settled before any of this runs

Per row, the plan requires a mechanism *plus a bootstrap and restore path*. This document supplies
the mechanism recommendation only. Still unnamed for every row:

1. **Bootstrap** — how a fresh node obtains the artifact the first time.
2. **Restore** — how to put a specific artifact back in the tree if the decision is reversed.
3. **Retention** — what guarantees the mesh copy is not the only copy.

And one gate the plan states that this document cannot discharge from here:

> **Gate:** confirm the mesh path + retention before removing anything from the tree. Beats
> specifically must keep serving `/media/beats` for the voice pipeline — validate that path is
> live first.

**That validation has not been done.** It needs a node with mesh access. Row 3 is written
conservatively (LFS rather than removal) precisely because I could not confirm it.

---

## Explicitly not in scope

- **No history rewrite.** The plan drops that premise and this document does not reintroduce it.
  Every mechanism here affects the *current tree*; repository history keeps its bytes either way,
  so none of this shrinks a full clone's history until and unless that separate decision is made.
- **The repo stays public.** This is clone hygiene, not a privacy action.
- Stage B and Stage C remain blocked on their own open decisions.
