# Jev × EvoSwarm Jive + HF-Agent Selection Presenter

**Date**: 2026-10-15 · **Lane**: JEV-PRIMARY WAVE (claimed 18:05Z) · Addendum to the use-case reconciliation doc.

## Part 1 — EvoSwarm jive (the architecture already fits)

EvoSwarm (`.claude/context/evoswarm.md`): Controller :8113 polls CGPs from Supabase → evolves parameter genomes (genetic algorithm) → publishes packs on NATS `geometry.swarm.meta.v1` → consumers (PMOVES.YT, **LangExtract**, Media-Video Analyzer, Hi-RAG v2) rebuild/decode → telemetry loops back as fitness.

AgentJev's `temperatures.json` **is already a parameter genome**: per-decision-type calibrated temperatures (boolean 1.072/n=180, choice 1.035/n=180, score 1.072/n=240, soft-CE per type). The jive needs zero new architecture:

1. **Jev consumes swarm packs** — the classifier's temperature/threshold set becomes just another consumable parameter pack on `geometry.swarm.meta.v1`. EvoSwarm evolves classification calibration exactly like CGP construction params. Verdict sealed with the pack's generation id → provenance includes *which evolution produced the classifier that made this call*.
2. **Jev verdicts feed fitness** — sealed classification telemetry (UNDECIDED rate, per-class confidence spread, agreement with auditor ground truth on DRIFTED re-reads) publishes to the Supabase geometry tables the Controller already polls. A classifier that abstains less while staying accurate raises swarm fitness. Calibration becomes **continuously evolved at test time** — the EvoSwarm thesis, applied to decision models.
3. **Same trust root** — verdicts and packs both CHIT-signable; the swarm's parameter provenance and the classifier's verdict provenance land in the same verification story. No skew: neither side edits the other's source, both evolve through sealed packs.

Wiring order when the lane opens: (a) publish current temperatures.json as pack v1 (manual, one-shot), (b) classifier reads pack from NATS/Supabase with local fallback, (c) emit verdict telemetry rows, (d) let the Controller treat classification fitness as a new objective. Steps a–b are a day; c is hours; d is the Controller-side lane (5090/evo owner).

## Part 2 — HF agent selection presenter (trio-of-options for model picks)

`pmoves-hf-researcher` currently returns ranked candidate lists. The presenter upgrade makes selections **Jev-style decision objects**: same `[STATE]/[Q]/[OPT]` trio shape, same multiple-choice scoring head, same sealed verdict records.

- **State** = the task spec (node capacity class, license constraints, context budget, measured VRAM from the census).
- **Options** = the HF candidate models (2–5 real candidates from the live search — never synthetic).
- **Verdict** = per-candidate logit → softmax → pick + confidence; <0.5 → UNDECIDED with the shortlist shown anyway (the human decides; the model never pretends).
- **Seal** = sha256 chain over (state, options, logits, chosen) → appended to the research analysis, same as drift reports. The selection becomes auditable: *why did we pick Gemma over Qwen on SPARK?* has a sealed answer with its probability distribution.
- **EvoSwarm tie-in**: over time, selection verdicts whose predictions were falsified by deployment reality (model too big for the node, license blocked) feed the same fitness loop — the selector evolves.

Zero new inference infrastructure: same onnxruntime + AgentJev pattern already proven in the auditor; keys stay in the funnel for the HF *search*, never for the *decision* (that's local and frozen). Operator's 'keys available' noted — they unlock candidate *retrieval* breadth on Spark, not judgment.

## Part 3 — v4 baseline (honest numbers)

- Verdicts: 198 claims → 117 VERIFIED / 80 UNDECIDED / 1 DRIFTED (digest `8ede091bbdc8…`) — identical to v3, **correct by design**: Jev classifies intent, reality probes classify drift. No interference between the two layers.
- Classification: 123 DRAFT / 15 RUNBOOK / 60 UNDECIDED across records; zero mixed-class docs; 10 docs fully abstained. Soft probabilities (choice calibration soft-CE 0.966 = near-uniform by design) mean the 0.5 gate abstains honestly on ambiguous docs rather than guessing — the fail-closed brand, now model-powered.
- Architecture decoded this session from the ONNX signature: multiple-choice scoring head (`input_ids [num_candidates, seq_len]` + `cand_end_pos` → `logits [num_candidates]`) — all options scored in one pass, which is *why* it runs at 129ms. The original 3/3 baseline's prompt shape was reverse-engineered and restored.
