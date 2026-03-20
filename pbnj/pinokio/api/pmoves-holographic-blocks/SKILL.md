---
name: PMOVES Holographic Blocks
description: |
  Quantize DARKXSIDE audio beats into Holographic CHIT Geometric Blocks via the Gemini
  multimodal embedding pipeline. Embeds raw .wav/.mp3 files as multi-dimensional topological
  arrays on the geometry.cgp.v1 bus, transpiles them to A2UI animation specs for Remotion,
  and optionally feeds the geometry into Unsloth or PMOVES-autoresearch for model fine-tuning.
keywords: chit, geometry, beats, audio, holographic, multimodal, gemini, unsloth, autoresearch, hi-rag, a2ui
version: 1.0.0
category: Media/AI/Geometry
---

# PMOVES Holographic Blocks

**Category**: Media/AI/Geometry  
**Version**: 1.0.0  
**Status**: Phase 11 — Active Development  
**Aligns With**: DARKXSIDE / Cataclysm Studios Three-Entity Doctrine

## Overview

Transforms mathematically engineered audio (beats, scales, BPM, EQ, compression topology) 
from the DARKXSIDE archive into reusable **Holographic CHIT Geometric Blocks** stored in 
the Neo4j/Supabase ShapeStore.

The pipeline is:
```text
Audio File (.wav/.mp3)
  → Gemini Multimodal Embedding (Hi-RAG)
  → geometry.cgp.v1 NATS event (Holographic Block)
  → ShapeStore (Neo4j + Supabase)
  → chit_a2ui_bridge.py (A2UI spec)
  → Remotion Renderer (a2ui-renderer)       [optional: visual proof]
  → Unsloth fine-tune OR autoresearch seed  [optional: model builder]
```

These geometric blocks are **structural** — not decorative. Agents (Agent Zero, Gemini CLI)
can read them as foundational topology for UI construction, smart contract flows, or DAO
proposal scaffolding.

## Capabilities

- Ingest a single `.wav` or `.mp3` file and emit a `geometry.cgp.v1` Holographic Block to NATS
- Batch-ingest a folder of beats (e.g., Google Drive archive)
- Transpile an existing CGP block into an `a2ui.animation.v1` spec via `chit_a2ui_bridge.py`
- Push CGP constellations into Unsloth for audio-geometry model fine-tuning
- Seed PMOVES-autoresearch with block coordinates for hypothesis generation

## Trigger Phrases

| Natural Language Phrase | Action | Script |
|-------------------------|--------|--------|
| "ingest beat [file]" | Embed single .wav/.mp3 → ShapeStore | `ingest-beat.js` |
| "ingest beats folder [path]" | Batch embed folder → ShapeStore | `ingest-batch.js` |
| "visualize block [block_id]" | CGP block → A2UI spec | `visualize-block.js` |
| "tune unsloth with beats" | Feed ShapeStore coords → Unsloth | `unsloth-geotune.js` |
| "seed autoresearch with beats" | Feed coords → autoresearch | `autoresearch-seed.js` |
| "list holographic blocks" | Query ShapeStore for existing CGPs | `list-blocks.js` |

## Mathematical Geometry Mapping

Each beat is decomposed along these axes before embedding:

| Audio Feature      | Geometric Axis | CGP Property         |
|--------------------|---------------|----------------------|
| BPM / Tempo        | Phase velocity | `geometry.delta`     |
| Root Scale / Key   | Topology class | `anchors[].coords.x` |
| Emotional register | Curvature κ    | `geometry.kappa`     |
| EQ high-shelf dB   | Spectral freq  | `spectral_signatures[].frequency_hz` |
| Compression ratio  | Amplitude ρ    | `spectral_signatures[].amplitude`    |
| Timbre character   | Holographic signature | `metadata.timbre_vector` |

> A sad scale at 60 BPM produces a different geometric knot than the same scale at 120 BPM.
> Both are valid, distinct, reusable building blocks.

## API Endpoints Required

| Service | Endpoint | Purpose |
|---------|----------|---------|
| Hi-RAG v2 GPU | `http://localhost:8087/hirag/ingest/audio` | Multimodal embedding |
| NATS | `nats://localhost:4222` | Publish `geometry.cgp.v1` |
| Supabase | `http://host.docker.internal:65421/rest/v1` | ShapeStore persistence |
| Neo4j | `bolt://localhost:7687` | Constellation graph storage |

## Environment Variables Required

```env
HI_RAG_GPU_URL=http://localhost:8087
NATS_URL=nats://nats:pmoves@localhost:4222
SUPABASE_URL=http://host.docker.internal:65421
SUPABASE_SERVICE_ROLE_KEY=<from supa-status>
NEO4J_URL=bolt://localhost:7687
NEO4J_PASSWORD=<from env.shared>
CHIT_PROD_PASSPHRASE=<required for CGP signing>
```

## Cross-Machine Access (Tailscale Mesh)

The Gemini CLI Pinokio instance on any machine in the mesh can run this skill:
```text
5090 (GPU embed):   http://100.x.x.x:8087/hirag/ingest/audio
z890 (Neo4j):       bolt://100.x.x.x:7687
4090 (orchestrate): Runs Gemini CLI → invokes skill via P7 Interpreter
```

## Integration Points

- **NATS Subject**: `geometry.cgp.v1` (emit), `geometry.visualization.request.v1` (visualize)
- **A2UI Bridge**: `pmoves/tools/chit_a2ui_bridge.py`
- **ShapeStore**: Supabase `pmoves_core.chit_shapes` table + Neo4j `(:CHITBlock)` nodes
- **Unsloth Fine-tune**: Feeds `(bpm, scale_root, kappa, amplitude)` tuples as training geometry

## See Also

- [`chit_a2ui_bridge.py`](../../../../pmoves/tools/chit_a2ui_bridge.py)
- [`AGNOTE4482.BEATS.md`](../../../../pmoves/docs/AGENTS/AGNOTE4482.BEATS.md)
- [`CATACLYSM_STUDIOS_INC.md`](../../../../pmoves/docs/PMOVESCHIT/CATACLYSM_STUDIOS_INC.md)
- [`botz-skills.md`](../../../../pmoves/docs/geometry-bus/services/botz-skills.md)
- [`pmoves-services/SKILL.md`](../pmoves-services/SKILL.md)
