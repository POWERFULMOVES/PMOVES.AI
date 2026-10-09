# Evo Controller on SPARK — deep dive and the shape-fitness opportunity

**Node:** SPARK (GB10) · **Date:** 2026-09-14 · **Lane:** evo-controller deployment + deep dive
**Trigger:** operator — "Spark made for evo controller, has shape workers; take the opportunity
to deep dive evo controller work in light of PMOVES enhancements."

## What is deployed (as of this lane)

`pmoves-evo-controller-1` — Up, healthy, `:8113` (localhost-bound), profile `orchestration`
(the reason `overlay-up-agents` alone never started it). Bus wiring: Supabase REST via kong
(+service-role key, funnel `_FILE` pattern), CHIT fail-closed signing
(`CHIT_REQUIRE_SIGNATURE=true`), Agent Zero events publish, NATS. First tick threw a transient
ConnectError during the recreate window; kong and agent-zero both answer from inside the
container now. The placeholder tick (below) should be observed green on subsequent 300s ticks.

Not deployed anywhere yet: `agentgym-rl-coordinator` (:8114) — the RL lane's counterpart
service that `agentgym_integration.py` targets.

## Current state of the code (honest read)

- `app.py` (402 lines): EvoSwarmController polls recent CGPs (`geometry_cgp_v1`, CHIT-signature-
  verified), then upserts a **hardcoded draft pack** (`K:8, bins:32, tau:0.2, beta:0.7`,
  `status: draft`, `pack_type: cg_builder`) and publishes `geometry.swarm.meta.v1` via Agent
  Zero. Its own docstring: "Real fitness logic will replace this placeholder."
- `agentgym_integration.py` (499 lines): the more forward-looking half — plateau detection,
  population-based training bookkeeping, ScalingInter-RL progressive horizon scaling, PPO
  defaults — all pointed at a coordinator that is not running.
- The wiring is proven end-to-end; the intelligence is stubbed.

## What changed in PMOVES since this was written — the inputs now EXIST

The service was written when shape traces were doctrine (`THREE_BODY_DOCTRINE.md`, Feb 2026).
Since then:

1. **`shape.trace.recorded.v1` is LIVE** — persona-thirdref (deployed 2026-09-13, round-trip
   proven: consumption → trace with enrichment) now emits real traces into the bus. The
   three-body "every trace is gravity" line has an actual gravity source.
2. **Shape profiles accumulate** — `shape.profile.updated.v1` fires at the
   `PERSONA_THIRDREF_PROFILE_THRESHOLD` (default 10 events).
3. **Third-ref theory is banked** — Levin boundness spectrum ↔ resonance/homogeneity,
   dissonance-as-max-information (Kuramoto/chimera), EMA profiles, co-consumption index,
   divergence events, diversity term (cipher memory, persona lane).
4. **Model-suits are real** — per-model profiles (`pmoves/configs/model-suits/`) and the
   2026-09-14 onboarding doctrine: harness tuned around the model, grounded personas,
   drop-in-safe siblings.
5. **Spynel is registered** (fork + lane, #3047) — the coming cross-agent surface for sharing
   what nodes learn.

## The opportunity: fitness = f(shape traces)

The placeholder's replacement should not be hand-tuned CGP heuristics. It should score
parameter packs against the **live shape-trace stream**:

- **Diversity term**: fitness rewards packs that keep the trace population diverse
  (anti-homogeneity; Levin's unbound end), using the banked dissonance framing — slightly
  off-phase configurations carry the most information.
- **Divergence events**: when a profile's EMA diverges sharply, that's a signal to explore,
  not exploit — the chimera edge.
- **Co-consumption index**: traces sharing sessions/items indicate healthy coupling between
  human and agent bodies — the stabilization the doctrine wants to measure.
- **Distillation closes the loop**: `shape.distillation.requested.v1` exists as a schema
  (`pmoves/contracts/schemas/shape/`). The controller's packs should be what distillation
  materializes: tuned params → persona/context priming → the model experiences the difference
  → new traces → next generation. That is the three-body orbit, executable.

## North star (operator vision, 2026-09-14, banked verbatim-in-spirit)

A model enters in a CLI, jumps into its harness, calls A0 to ask Archon to **mint a custom
harness tuned for that model** (e.g. a perfect DeepSeek harness). Local models additionally
get **weight changes** (fine-tuning; GB10 can LoRA). Cloud models and local models
**cohabitate, helping their local peers**. A0 and Archon share the registry; every agent can
call the others. SPARK goes to school (watch + verify + learn from the evo/RL video corpus)
and shares knowledge back to the pool; once PMOVES-Spynel is up, Archon's mints propagate to
the whole ecosystem. Weird science, super cool — and each piece already has a rail:
registry (shared), minting (Archon factory), harness requests (A0 → Archon), tuning
(evo-controller + shape traces), weights (GB10 LoRA lane, open).

## Gap list (ordered)

1. **Real fitness consumes shape traces** — subscribe `shape.trace.recorded.v1` +
   `shape.profile.updated.v1` in the controller; score packs against them (design deltas
   above). The placeholder keeps running until the fitness scorer beats it.
2. **`agentgym-rl-coordinator` deployment** — the RL half is dead code until it exists;
   decide node placement (SPARK is the natural home).
3. **School queue** — the evo/RL watch-list lives in the enrichment DB on the 5090
   (`pmoves_core.youtube_videos`, `wealth_topic='ai-ml'` + evolution/reinforcement/open-ended
   title filters; NOT on SPARK's local supabase — verified absent here). Pull the shortlist,
   transcribe on SPARK's now-working yt→whisper pipeline (Cole Medin lane proved it), map
   learnings like the Archon map (#3050).
4. **Supabase shape tables** — traces fire on NATS; check whether `shape_*` tables exist to
   persist them (the CGP fetch pattern shows the persistence idiom).
5. **Weights lane** — GB10 LoRA/Unsloth path for local models (ties to the standing
   Unsloth-on-5090 gap; GB10 arm64 needs its own verification).

## Provenance

- Deployed via `env -u NATS_URL make -C pmoves overlay-up-agents OVERLAY_PROFILES_AGENTS="--profile agents --profile orchestration"`
- Code read at `pmoves/services/evo-controller/{app.py,agentgym_integration.py}` @ main `85690e6c8`
- Shape schemas: `pmoves/contracts/schemas/shape/{trace,profile,distillation}.*.v1.schema.json`
- Related doctrine: `pmoves/docs/PMOVESCHIT/THREE_BODY_DOCTRINE.md`,
  `pmoves/docs/AGENTS/AGNOTE4482.md` §Onboarding (positive-sum door)
