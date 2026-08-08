# CHIT Tour Living-Docs Update Plan — Dirichlet/Latent-Geometry drop (view v1, 2026-08-08)

> Source: `SEAP/Integrating Dirichlet Distributions and Latent Geometry into
> PMOVES.AI.pdf` — NOTE: byte-identical to `SEAP/DARKXSIDE-deep-research-report.md`
> (one drop, two filenames). This is the review view; edits ship only after
> operator sign-off.

## Headline

The drop does two things: (1) **adds** the belief-over-geometry composite —
every manifold point carries a Dirichlet belief state (`π ~ Dir(α)`) with an
inspectable envelope (alpha, mean, concentration, entropy, provenance hashes);
(2) **corrects six overclaim families** currently shipping in CHIT docs, with
recommended replacement wording.

## Corrections required (claim → where it ships → fix)

1. **"Dirichlet guarantees fair non-zero weight (α≥1)"** — GLOSSARY:29,
   WHAT_IS_CHIT:83, CGP spec:58/69 → α≥1 guarantees neither fairness nor
   minimum influence; fairness needs explicit constraints + outcome audits.
2. **"Exponential storage capacity" (Poincaré)** — spec:38/51/76,
   WHAT_IS_CHIT:85 → metric *volume* grows exponentially ≠ more stored bytes;
   O(log n) distortion needs theorem citation + tree class or removal.
3. **"Tamper-proof attribution"** — GLOSSARY:37, WHAT_IS_CHIT:87,
   spec:52/97, VISUAL_TOUR:485 → "tamper-**evident** inclusion proof under the
   stated trust model" (Merkle proves inclusion, not authorship).
4. **"Universal translatability / telepathy-like"** — spec:35/40 →
   "corpus- and embedding-conditioned geometry-only retrieval"; metaphor only
   in labeled vision material.
5. **"Exact mode — lossless"** — WHAT_IS_CHIT:70, spec:449 → exactness comes
   from the retained payload; geometry-only is lossy until proved otherwise.
6. **"Production Ready" + zeta-filter claims** — spec:9/877, GLOSSARY:57 →
   maturity-ladder labels (prototype/evaluated/hardened/candidate/certified);
   zeta = experimental pending ablations.

## Additions (technical docs, NOT the public tour)

- Belief-envelope schema (`belief_type: dirichlet.v1`) as an optional
  versioned CGP §uncertainty block; canonical-JSON-before-signing requirement;
  AES-GCM confidentiality scope vs HMAC integrity separation.
- Seven proposed NATS subjects (`geometry.belief.updated.v1` etc.) appended to
  02_GEOMETRY_BUS.md **as a clearly-marked Proposed table** — none exist on
  the bus today; presenting them as live would violate verified-actuals.
- New `06_EVIDENCE_LEDGER.md` for the adversarial test matrix + calibration
  metrics (ECE/Brier/NLL) instead of bloating the tour.

## Tour changes (minimal, high-leverage)

- **Beat 3 only** content change: pillars 1+2 reframed as one composite —
  "the shape says *where*, the Dirichlet says *how sure*."
- **New Beat 3b (interactive)**: ternary-simplex lab in `pillars-lab.js` —
  α sliders, posterior-mean marker, sampled particles; teaches ratios-move-
  the-mean / scale-shrinks-variance / α<1 favors corners / sample ≠ mean.
- **Hover-evidence legend** across the constellation renderer: every artistic
  mark reveals α, mean, entropy, coords, model version — the drop's UX
  doctrine: "the experiential view never silently substitutes metaphor for
  evidence." Beats 1–2 and 4–10 unchanged; the two-meaning canon is intact.

## Registry gap

`00_GLOSSARY.md`, `01_WHAT_IS_CHIT.md`, `CGP_v1.0_SPECIFICATION.md` carry the
contradicted claims but are NOT in `living_docs_registry.yaml` — add them, or
they keep drifting with no reconcile check.

## Sequencing (proposed)

1. Claim-correction text pass (six docs, no code) — unblocks everything.
2. Registry-track the three untracked CHIT docs.
3. Tour beat-3 reframe + simplex lab + hover legend.
4. Belief-envelope schema + subjects, gated behind actual implementation.

## Caution

The drop's own "verified" column audited only a rendered spec via web view
(it says so) — re-verify every path locally before promoting anything out of
Proposed. All `pmoves_math/**` paths, contracts, notebooks it references are
proposals, and every performance claim is hypothesis (≥5 seeds + CIs before
any number reaches a doc).
