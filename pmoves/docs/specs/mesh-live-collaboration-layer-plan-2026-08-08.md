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

**Mechanism:** git-hygiene move (git-lfs pointer OR remove-from-tree + mesh path), source-of-truth on
`/media` (beats/audio) and `/business` (decks). **This is the only "removal" — clone hygiene, nothing
deleted from the mesh.**

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

**This is its own follow-up** — a data/verification lane, not part of the Stage A binary offload.

---

## Parked (operator wiring decision, not built against)

- `archon.crawl.*` subject retirement — speculative contract neither project implemented
  (publish→echo circuit, no fetch). Retire vs let a VL service define its own contract — **operator's
  call.**

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
