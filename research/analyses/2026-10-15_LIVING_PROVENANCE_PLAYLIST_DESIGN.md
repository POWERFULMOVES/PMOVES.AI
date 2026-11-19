# Living Provenance for the Playlist — the Kaleidoscopic Corpus

**Date**: 2026-10-15 · **Lane**: CHIT TOOLING REVIEW / provenance design (claimed 17:50Z) · Builds on: L5 reverse index (2026-10-12_JEV_CORPUS_REPO_MAP.md), chit-tour SOURCES pattern, drift auditor v3.

## The vision (operator's frame, grounded)

> "citations for living provenance like a window to the source with proper lens not skewed, super grounded, with knobs that shift the view along tangent related — like a kaleidoscopic hologram"

**The discovery: PMOVES already built this pattern — on the chit-tour site.** `website/chit-tour/data.js` carries a SOURCES map where every UI claim points at its repo path, and `pillars-lab.js` computes every number live with the repo's own parameters, stating plainly where code differs from prose. That's the standard. The playlist corpus just needs the same treatment.

## What exists today (the iceberg's visible tip)

| Layer | Asset | State |
|---|---|---|
| Transcript | 68+ files, research/transcripts/ | raw text, videoId-keyed ✅ |
| Analysis | 50+ files, research/analyses/ | claims cited to transcript ✅ |
| Reverse index | 30-video videoId→transcript→analysis→repo-artifacts | JEV_CORPUS_REPO_MAP, needs refresh cadence |
| Citation window | chit-tour SOURCES map | repo-path per claim ✅ (site only) |
| Drift watch | runbook_drift.py v3 + weekly task | covers plans/; corpus + SOURCES not yet |

## The design: four lenses, one window

Every claim in the corpus becomes queryable through four lenses — the knobs that shift the view without moving the source of truth:

1. **By-source** (the window): every analysis claim carries `videoId @ timestamp` + transcript path + repo artifact path. Click-through opens the source, never a paraphrase-of-a-paraphrase. Format: the existing `[N]` citation discipline from NotebookLM, grounded to files.
2. **By-artifact** (the reverse index): videoId → which repo artifacts it informed → which PRs/commits landed them. Answers: "which video is this lane standing on?" — the JEV_CORPUS_REPO_MAP becomes a generated view, not a hand-kept doc.
3. **By-decision-model** (Open Jev lens): which claims were classified/validated by which local model (AgentJev, Open-Jev DeBERTa, Layla, Needle3) with confidence — the model-view is honest about its own UNDECIDEDs.
4. **By-time** (the drift lens): which claims were verified when, by which scorer generation, with the v1→v2→v3 correction history preserved. Provenance includes *the auditing of the provenance*.

**Deliberate non-skew guarantee:** lenses share one sealed store (the existing transcript+analysis files + a generated index). Lenses are views; the window never edits the source. Crawl snapshots (video counts, dates) are marked snapshot-at-crawl and re-verified at use — the existing corpus discipline, now enforced by the drift auditor instead of by memory.

## Implementation shape (v3.1, mostly assembled already)

- `scripts/runbook_drift.py --globs 'research/analyses/*.md,website/chit-tour/data.js'` — the auditor extends to: every transcript path cited in analyses exists; every SOURCES path in chit-tour exists; every videoId in the reverse index has transcript + analysis. The kaleidoscope gets its own drift watch — folded into the weekly task.
- Generated view: `research/corpus_index.json` — built from the same extractor family (zero LLM), sealed with the same hash chain, four lens keys per record (source / artifacts / models / time).
- Surfacing: chit-tour-style static page (the site pattern exists: `website/` + wrangler) OR OpenNotebook panel; both read the same sealed index. No new truth store — the window is generated, never hand-written.
- Open Jev review folds in here: the iceberg reflection (orgsim fork pattern + Open Jev family + transcribe/fetch tooling) becomes lens 3's reference implementation — his "core learner, optional frozen-weight backbone" is exactly lens 3's architecture.

## Spark extract worker hook

The Spark Claude langextract worker (`.claude/commands/langextract/` on the host: extract/process/provider/status) is the production ingestion edge for this pipeline. Design contract when wiring: worker output lands as transcript-adjacent claims in the same sealed format, so everything Spark extracts enters the corpus THROUGH the provenance window — never around it. Probe of the worker's live state is queued as this lane's next step (host CLI).
