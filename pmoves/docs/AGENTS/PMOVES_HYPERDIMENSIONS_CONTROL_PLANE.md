# PMOVES Hyperdimensions Control Plane Taxonomy
_Last updated: 2026-02-15_

This document defines how `Pmoves-hyperdimensions` is used in PMOVES as:

1. a geometry map/illustration surface for operators and personas, and
2. a control plane that maps latent geometry signals to runtime LLM/service parameters.

## Source documents

This contract is grounded in:

- `pmoves/docs/PMOVESCHIT/CHIT_IMPLEMENTATION_AUDIT_2026-02-08.md`
- `pmoves/docs/PMOVESCHIT/Integrating Math into PMOVES.AI.md`
- `pmoves/docs/PMOVESCHIT/Human_side.md`
- `pmoves/docs/PMOVESCHIT/Latent_Geometry_Is_a_Control_Knob/Latent Geometry as a Control Knob_ Evidence from Five Compact Experiments.md`
- `pmoves/docs/MODEL_SOURCE_OF_TRUTH.md`
- `pmoves/docs/CHIT_AUDIT_TRACKING.md`
- `pmoves/docs/PMOVESCHIT/GEOMETRY_BUS_INTEGRATION.md`

## Position in the PMOVES taxonomy

This extends `pmoves/docs/AGENTS/PMOVES_UNIFIED_AGENT_TAXONOMY.md`:

- `L2 Bus + Routing`: geometry packet transport (`geometry.cgp.v1`)
- `L3 Swarm Intelligence`: pack/meta feedback (`geometry.swarm.meta.v1`)
- `L4 Modal Intelligence`: text/audio/VLM observers produce geometry metrics
- `L5 Memory + Safety`: Supabase registry + CHIT persistence

Hyperdimensions acts as `L2.5`, between routing and swarm adaptation:

- render current latent state
- expose operator-safe control knobs
- emit parameter deltas to services through existing APIs/events

## Canonical runtime contract

## Envelope and schema normalization

Use one transport envelope across services:

```json
{
  "type": "geometry.cgp.v1",
  "data": {
    "spec": "chit.cgp.v0.2"
  }
}
```

Rules:

- Transport event remains `geometry.cgp.v1`.
- Payload `data.spec` should converge to `chit.cgp.v0.2` (or `v0.1` during migration).
- Do not introduce new custom variants like `cgp.v1` for fresh implementations.

This addresses the schema divergence called out in `CHIT_IMPLEMENTATION_AUDIT_2026-02-08.md`.

## Geometry state vector

Hyperdimensions control plane uses a compact state vector:

- `delta_proxy` (`delta`): tree-likeness proxy (from latent geometry experiments)
- `curvature_k` (`kappa`): hyperbolic/ricci curvature signal
- `spectral_entropy_z` (`Hz`): zeta-filtered spectral entropy
- `swarm_fitness` (`F`): EvoSwarm fitness from `geometry.swarm.meta.v1`
- `attribution_confidence` (`A`): CHIT confidence/proof completeness

Current Hyperdimensions save format already exposes `delta_proxy` and `curvature` in:

- `Pmoves-hyperdimensions/saves/chit_manifold.json`

## Control mapping to runtime parameters

These mappings are a starting policy, not a fixed model lock. Model/provider choice must still flow from Supabase model registry.

| Geometry signal | Interpretation | Runtime action |
| --- | --- | --- |
| `delta` high | latent space less tree-like | lower generation randomness; increase retrieval grounding (`top_k`, rerank on) |
| `delta` low | latent space more tree-like | allow slightly more generative freedom while preserving grounding |
| `kappa` strongly negative | high hierarchy pressure | prefer hierarchical retrieval plans and chain threads |
| `Hz` high | noisy spectral profile | increase filtering/consensus passes before publish |
| `F` low | weak swarm policy fit | switch to safer/default pack and require replayable evidence |
| `A` low | weak attribution proof | block publish-to-user; keep in draft/review lane |

Recommended parameter surfaces to tune (service-level):

- decoding: `temperature`, `top_p`, `presence_penalty`, `max_tokens`
- retrieval: `top_k`, rerank enablement, lexical/dense weighting
- orchestration: thread shape (`B/P/C/F`), swarm pack selection, approval gates

## Function wiring (control-plane to services)

| Plane | Function/API | Role |
| --- | --- | --- |
| Geometry ingest | `POST /geometry/event` (gateway + hi-rag v2) | Accept CGP envelope and warm ShapeStore |
| Cross-modal jump | `GET /shape/point/{point_id}/jump` | Resolve modality locators from geometry point |
| Decode checks | `POST /geometry/decode/text`, `/geometry/decode/image`, `/geometry/decode/audio` | Observer-facing interpretation |
| Calibration | `POST /geometry/calibration/report` | Report entropy/divergence metrics for gating |
| Retrieval | `POST /hirag/query` | Apply geometry-aware retrieval + rerank path |
| Swarm feedback | `geometry.swarm.meta.v1` | Activate/deactivate decoder packs and tuning metadata |
| Voice return | `voice.agent.response.v1` | Flute/voice side uses same control outputs for narration style |

## Creator visualization contract

`PMOVES-Creator` should treat Hyperdimensions as an operator and persona visualization surface:

- map `delta`, `kappa`, `Hz`, `F`, `A` into visible controls/overlays
- keep one-click drill-down to geometry endpoints (`/geometry/*`, `/mindmap/*`)
- store per-run snapshots as replayable artifacts (no secret material)

Minimum display fields for each run:

- `shape_id`, `constellation_id`, `pack_id`, `namespace`, `source_event`
- geometry vector (`delta`, `kappa`, `Hz`, `F`, `A`)
- selected runtime profile (`service_model_mappings` row id/version)
- validation status (`pass`, `warn`, `block`) with reason

## Model source-of-truth binding

No hardcoded model IDs in this control plane.

Resolution order is fixed by `MODEL_SOURCE_OF_TRUTH.md`:

1. Supabase runtime registry (`pmoves_core.v_service_models`)
2. local manifests (`pmoves/models/*.yaml`)
3. operator overrides (`pmoves/.env.local`)

Hyperdimensions can change routing intent, but final model resolution must come from registry aliases/mappings.

## Production validation checklist

Use this sequence for audit evidence:

1. Bring-up + health:
   - `make -C pmoves up`
   - `make -C pmoves smoke`
2. Geometry path:
   - post a test `geometry.cgp.v1` envelope to `/geometry/event`
   - verify `/shape/point/{id}/jump` and `/geometry/calibration/report`
3. Swarm path:
   - verify `geometry.swarm.meta.v1` updates active packs in hi-rag v2
4. Model routing:
   - `make -C pmoves model-apply PROFILE=<profile> HOST=<host>`
   - `make -C pmoves models-registry-snapshot`
5. Observability:
   - confirm dashboards/logs include geometry + swarm + model-routing decisions

## Expansion backlog (next)

- Add a dedicated `hyperdimensions.control.v1` event (optional) that carries only normalized control vector updates.
- Add server-side normalization utility so all producers output `chit.cgp.v0.2` payloads.
- Add Creator widget spec in `PMOVES-A2UI` for the geometry control panel and replay timeline.
