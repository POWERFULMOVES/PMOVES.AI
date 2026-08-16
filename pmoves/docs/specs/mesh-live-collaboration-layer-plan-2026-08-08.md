# Plan — Mesh/JuiceFS as the Live Collaboration Layer

**Date:** 2026-08-08
**Author:** z890-claude (infra)
**Status:** Plan / decided layout. Stage A is actionable; Stages B and C are follow-up lanes.

---

## Framing (read this first)

This is **not a privacy purge**. It was mis-premised earlier as a history-rewrite / secrets-removal
job; that framing is **dropped**.

The repo is **public by design** — radical transparency, **no moat, no gatekeeper, no fake CHIT**.
Russell Richardson / DARKXSIDE is an **intentional public figure**; the financials stay public and
get **actualized** (real + CHIT-verified, not projections).

The point of the mesh (already live on z890's tailnet — layout `/docs`, `/media`, `/business`, …) is
to make content **living**: realtime, verifiable, **multi-portal like a room**, so agents + operators
get **fluid shared comms** across nodes instead of git round-trips. "Save time" here means **fluid
collaboration, not hiding.**

**Split principle:** by *what benefits from being live/shared* vs *what is versioned source*.

- **No history rewrite. No privacy purge.**
- The only "removal" is moving **large binaries** off git for clone hygiene — with the
  source-of-truth **living on the mesh** and served to every node.

---

## Stage A — Large binaries → mesh (actionable now)

Move the heavy binaries to the object store / mesh for git-hygiene; **keep the `.md` / `.csv` source
in git**. The mesh serves them live to every node.

| Candidate | Verified size / count | Note |
|-----------|----------------------|------|
| `pmoves/data/beats/soundcloud/darkxside/` | **98 MB** audio | Also feeds the beats/BPM voice pipeline live from `/media/beats` (see `shift-from-bpm`) |
| `CATACLYSM_STUDIOS_INC/` binaries | **125 MB** decks/CSVs | Keep `.csv`/`.md` source in git; move rendered decks/binaries |
| `pmoves/docs/evidence/` PNGs | **38 PNGs** (plan estimate of ~180 not confirmed — audit before bulk move) | Screenshots/evidence |
| `*.pdf \| docx \| pptx \| zip` renders | (sweep repo-wide) | Generated renders, not source |
| open-notebook `checkpoints.sqlite` | (binary state) | Runtime state, not source |

> **Reproducibility (4090, at merge).** The table mixes measured bytes, a file count, and one
> explicitly-unconfirmed estimate, with no audit command or observation date — the same
> unreproducible-number defect called out on the WS2 register sweep. Regenerate before acting:
> ```bash
> # tracked blobs over 1 MiB, largest first — excludes submodules by construction
> git ls-tree -r -l HEAD | awk '$4 > 1048576 {print $4, $5}' | sort -rn | head -40
> git ls-files 'pmoves/docs/evidence/*.png' | wc -l
> ```
> **Re-measured 2026-08-16 against `origin/main` @ `017de5369`** with the commands above: beats
> **98 MB**, `CATACLYSM_STUDIOS_INC/` **126 MB**, evidence PNGs **38** — the table's figures hold.
> The table nonetheless *under*-scopes the job: the full tracked surface is **75 blobs over
> 1 MiB totalling 259 MB**, and the single largest file (70.8 MB, under
> `CATACLYSM_STUDIOS_INC/evidence/`) is named by no row here. Scope Stage A from the command,
> not from the table.
>
> **Inclusion rule:** tracked files in this repository only. Submodule contents are out of scope
> (they are separate repos with their own hygiene), and generated files are in scope only where
> the generator is also tracked. Figures above were observed 2026-08-08 and are **not** re-verified
> at merge.

**Mechanism — OPEN DECISION, must be settled per artifact before Stage A is executable.**
`git-lfs pointer` and `remove-from-tree + mesh path` are not interchangeable: they differ in clone
behaviour, CI checkout cost, offline-node availability, and rollback. LFS keeps the path resolvable
everywhere at the cost of an LFS dependency in every clone and CI job; remove-from-tree makes the
artifact unavailable to any node that cannot reach the mesh. **Stage A cannot start until each row
of the table above names one of the two, plus its bootstrap and restore path.** Source-of-truth on
`/media` (beats/audio) and `/business` (decks). **This is the only "removal" — clone hygiene,
nothing deleted from the mesh.**

**Gate:** confirm the mesh path + retention before removing anything from the tree. Beats specifically
must keep serving `/media/beats` for the voice pipeline — validate that path is live first.

---

## Stage B — Living docs → mesh-backed, realtime, multi-portal (the supercharge)

The persona / financial / business docs **stay public and REAL** — made *living*: realtime-updating,
verifiable, multi-portal (pulling from other services the way a room pulls portals). This is where
"fluid agent+operator comms" lands: the mesh is the shared realtime surface, **git holds the
source/templates**.

Candidates:
- `pmoves/docs/research/persona/**`
- `CATACLYSM_STUDIOS_INC/**` financials → **actualized** (see Stage C — real + CHIT-verified, not
  projections; "no fake CHIT")
- generated living docs regenerated **on-mesh from git registries**: `UPDATE_NOTES.md`
  (**270 across the tree** incl. submodules), `LIVING_DOCS_INDEX.md`, catalogs, `research/` reports.
  Freshness rules already live in `pmoves/configs/living_docs_registry.yaml` (tracked by
  `make -C pmoves docs-reconcile-check`).

> **OPEN DECISION — the mesh-backed document contract must be specified before Stage B starts.**
> "git holds source/templates, mesh holds generated documents" is a split-brain design until five
> things are named, and none of them are named here:
> 1. **Writer** — which single process may write mesh documents, and what stops a second one.
> 2. **Update trigger** — regeneration on git push, on registry change, on a timer, or on demand.
> 3. **Atomic publish** — whether a reader can observe a half-written document, and the
>    write-then-swap rule that prevents it.
> 4. **Read-only?** — whether mesh output is strictly derived (any edit there is lost on the next
>    regeneration) or authoritative for some fields. If derived, say so loudly in the artifact
>    itself, because a living doc that looks editable will be edited.
> 5. **Divergence detection + repair** — `docs-reconcile-check` today checks freshness of tracked
>    files. It has no notion of a mesh copy, so it cannot detect git/mesh divergence at all.
>    Extending it is Stage B work, not an assumption Stage B can make.
>
> Until these are settled, Stage B is a direction rather than an executable plan.

**Follow-up lane** — needs the mesh regeneration harness designed before moving generated docs.

---

## Stage C — Actualize the financials (substantive lane, not a file move)

The CATACLYSM financials should be **real and verified**, not sitting projections. This connects to
the **domino / value-engine thesis** (verified → CHIT-signed → real value).

> **Correction (4090, at merge).** This originally cited
> `pmoves/docs/specs/value-engine-domino-v0-spec-2026-08-07.md`. **No such file exists**, at
> this commit or under any renamed equivalent — a repo-wide filename and content search
> returns nothing. The thesis currently lives only in the
> `[[vision_value_engine_dominos_victory_stories]]` memory, which is node-local and not
> readable by whoever picks this lane up. **Writing that spec is therefore Stage C's first
> task, not a reference it can lean on** — until it exists, Stage C has no recoverable
> requirements.
>
> **Update (2026-08-16).** That is now out of date in the good direction: the spec exists as
> `spec/value-engine-domino-v0`, open as **PR #2516** and not yet merged. Stage C is
> therefore blocked on a *merge*, not on an authorship gap. Re-read the spec as merged before
> planning against it — an open PR can still change shape in review.

**This is its own follow-up** — a data/verification lane, not part of the Stage A binary offload.

---

## Parked (operator wiring decision, not built against)

- `archon.crawl.*` subject retirement — speculative contract neither project implemented
  (publish→echo circuit, no fetch). **Status: PARKED, delegated to Archon** (which has live NATS
  visibility; z890 could not reach `localhost:8222`). Archon observes for any real publisher or
  subscriber on `archon.crawl.request.v1` / `archon.crawl.result.v1` and retires if none, or lets a
  VL service define its own contract. Recorded in `AGNOTE4482PHI.t1.md` under
  `Z890-CLAUDE::CONTROL-ITEMS-RESOLVED-2026-08-08`. **`.claude/context/nats-subjects.md:1798-1799`
  (was `:1776-1777` when this plan was written — the file has grown; re-locate by subject name,
  not by line) still documents both subjects with no status marker — whoever executes the retirement owns that
  edit; this plan does not pre-empt it.**

---

## Verification (from the plan)

- [ ] Mesh layout decided: **live/shared vs versioned-source** (this doc).
- [ ] Large binaries served from mesh; **source `.md`/`.csv` stays in git**.
- [x] Repo stays public.
- [x] **No history rewrite.**

## Execution order

1. **Stage A** — large-binary offload first (clone hygiene). Gate on mesh path + retention confirm.
2. **Stage B** — living-docs mesh regeneration (needs harness design).
3. **Stage C** — financial actualization (ties to the value-engine lane).
