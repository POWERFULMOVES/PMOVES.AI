# CHIT Evolutionary Sidecar Roadmap

Date: 2025-10-17

This note consolidates the integration plan for (1) the EvoSwarm controller, (2) CGP builder parameter packs, and (3) the GAN sidecar gatekeeper. Each section captures the objective, initial implementation steps, telemetry expectations, and review notes for follow-on work.

## 1. EvoSwarm Controller Service

**Objective:** Continuously evolve geometry-generation and decoding hyperparameters using calibration metrics and energy telemetry.

- **Service skeleton**
  - Location: `services/evo-controller/` (new FastAPI worker).
  - Inputs: Supabase tail of recent CGPs, `/geometry/calibration/report`, optional NVML energy samples (if GPU present).
  - Loop cadence: every 5 minutes pull last N packets, evaluate fitness, emit revised parameter packs.
- **Genome definition**
  - `cg_builder`: `{K, bins, tau, beta, spectrum_mode, mf_rank}`.
  - `decoder`: `{mode, hrm_halt_thresh, hrm_mmax, gan_weight}`.
  - `energy`: `{nvml_avg_watts, duration_ms}` (for Pareto ranking).
- **Outputs**
  - Publish to Supabase table `geometry_parameter_packs` with `status=active` and to NATS as `geometry.swarm.meta.v1`.
  - Include provenance (`population_id`, `best_fitness`, `timestamp`).
- **Review notes**
  - Confirm Supabase schema before coding.
  - Define fallback defaults if no viable genome improves fitness.
  - Align with security policy—parameter packs should be signed when `CHIT_REQUIRE_SIGNATURE=true`.

## 2. CGP Builder Parameter Packs

**Objective:** Teach ingestion services to consume EvoSwarm-tuned packs when producing CGPs.

- **Consumer pattern**
  - Add helper (shared in `services/common/geometry_params.py`) to fetch latest `cg_builder` pack by namespace/modality.
  - Cache locally with TTL (e.g., 10 minutes) to avoid hot Supabase loops.
- **pmoves-yt integration**
  - Update `_build_cgp()` to use pack values (K, bins, tau, beta) and optional MF projections instead of static spectrum.
  - Persist `pack_id` in CGP `meta` for traceability.
  - Emit calibration payload after each CGP to feed controller loop.
- **Other services**
  - LangExtract and media-video follow same helper—document once to avoid divergence.
- **Review notes**
  - Coordinate with DB team on `geometry_parameter_packs` table (versioning + status flags).
  - Add unit tests that mock pack retrieval and validate fallback path.
  - Ensure packs survive offline mode: default YAML in repo for cold start.

## 3. GAN Sidecar Integration

**Objective:** Add a lightweight checker that validates/edits geometry decodes before returning to callers.

- **Placement**
  - Module: `services/hi-rag-gateway-v2/sidecars/gan_checker.py`.
  - Exposed via `geometry.decode.text` (new `mode:"swarm"`) and optionally `geometry.decode.image`.
- **Functionality**
  - Rerank candidate summaries or media URLs using rule-based + small-model scores.
  - Provide structured critique (`format_ok`, `safety_score`, `hint`) for optional HRM refinement pass.
  - Allow `max_edits` = 1 by default; escalate to error if still below threshold.
- **Telemetry**
  - Log pass/fail counts, average critique categories, and attach to CGP `meta` when decode succeeds.
- **Review notes**
  - Decide whether sidecar runs synchronously or via background Celery worker (latency vs. throughput).
  - Security: ensure sidecar enforces content policies consistent with Agent Zero.
  - Add feature flag `GAN_SIDECAR_ENABLED` for phased rollout.

## Open Questions for Follow-Up Review

1. Do we standardize energy telemetry collection (NVML vs. external sensors) across all GPU hosts?
2. Should EvoSwarm packs extend to ShapeStore parameters (capacity, eviction bias)?
3. How do we expose sidecar critique data to end users (Agent Zero dashboards vs. Supabase table)?
4. What governance is required to approve new genomes before they impact production workflows?

## Next Steps

1. Draft Supabase schema migration (`geometry_parameter_packs`, `geometry_swarm_runs`).
2. Scaffold `services/evo-controller` with placeholder fitness function calling `/geometry/calibration/report`.
3. Modify `pmoves/services/pmoves-yt/yt.py::_build_cgp` to load packs when available and attach `pack_id` to CGP meta.
4. Prototype GAN sidecar rerank logic and wire under feature flag.

---
_Notes compiled for immediate implementation and future review sessions._
