> **DEPRECATED — 2026-05-08**
> Pre-MOF advisory capacity model. ClaWZ was archived 2026-02-18; this doc's 6-layer fold model was superseded by the operational taxonomy in `PMOVES_AGENT_CLASS_TAXONOMY.md` (v1.5.0). Retained for historical reference.

# PMOVES Unified Agent Taxonomy
_Last updated: 2026-02-15 (deprecated 2026-05-08)_

This taxonomy unifies PMOVES agents, services, and personas into a single
operational model for production bring-up and long-running orchestration.

## Six-layer fold model

1. `L0 Identity Anchors`
- 325 persona anchors (grounded identities, not isolated agents).
- Anchors map to source evidence in `pmoves/docs/context` + approved media/doc sources.

2. `L1 Orchestrators`
- `PMOVES-Agent-Zero`: primary orchestrator.
- `PMOVES-Archon`: planning/execution copilot and multi-agent bridge.

3. `L2 Bus + Routing`
- Geometry Bus (`geometry.*` events), CHIT, and gateway routing.
- Purpose: deterministic context movement and jump/replay across services.

3.5. `L2.5 Hyperdimensions Control Plane`
- `Pmoves-hyperdimensions` provides geometry-state visualization and operator-safe control knobs.
- Purpose: map latent geometry signals (`delta`, curvature, spectral entropy) to runtime retrieval/decoding/swarm policy changes.
- Canonical contract: `pmoves/docs/AGENTS/PMOVES_HYPERDIMENSIONS_CONTROL_PLANE.md`.

4. `L3 Swarm Intelligence`
- EvoSwarm and role-based swarm packs.
- Purpose: protective/supportive specialist swarms per agent persona and task profile.

5. `L4 Modal Intelligence`
- Text LLM, audio/TTS/STT, and VLM observers.
- Purpose: multimodal reasoning, narration, and visual verification of tool execution.

6. `L5 Memory + Safety`
- Supabase, Neo4j, CHIT manifests, and secure persistence policy.
- Danger Room / training infra for safe experimentation and rollback.

## Canonical PMOVES planes

- `Control plane`: Agent-Zero, Archon, runner governance.
- `Context plane`: CHIT, geometry packets, persona anchor mappings.
- `Execution plane`: gateway tools, n8n automations, service adapters.
- `Observation plane`: logs/metrics/traces + VLM visual verification checks.
- `Safety plane`: secrets policy, signed artifacts, training sandboxes.

## Grounded persona lifecycle

1. Ingest source materials (video + docs from approved context sources).
2. Extract anchor traits and map them to persona graph nodes.
3. Bind persona to tool/memory policy and swarm profile.
4. Run supervised tasks with observability and safety gates.
5. Persist memory selectively (agent/user policy controlled).
6. Optionally publish back to source-of-truth stores.

## Geometry Bus demonstration path

1. Emit CHIT packet with anchor metadata.
2. Route through geometry bus (`geometry.cgp.v1`).
3. Spawn EvoSwarm profile tied to persona + task risk.
4. Execute via gateway tools with compact context handoff.
5. Validate with text + audio + VLM checks.
6. Persist approved memory/state with audit trail.

## Required validations per layer

- `L1`: orchestrator health + MCP reachability.
- `L2`: geometry event publish/consume and replay.
- `L3`: swarm policy load + fallback behavior.
- `L4`: text/audio/VLM tool execution verification.
- `L5`: secret hygiene, at-rest policy, and rollback proof.

## Control-plane references

- Hyperdimensions control-plane taxonomy:
  - `pmoves/docs/AGENTS/PMOVES_HYPERDIMENSIONS_CONTROL_PLANE.md`
- Geometry bus integration:
  - `pmoves/docs/PMOVESCHIT/GEOMETRY_BUS_INTEGRATION.md`
- Model source of truth:
  - `pmoves/docs/MODEL_SOURCE_OF_TRUTH.md`
