# CREATOR Pipeline Documentation

**Thread 7.1: PMOVES-Creator Generative Pipeline**

## Overview

The CREATOR pipeline manages generative content workflows through ComfyUI, connecting image generation, agent card art, and visual output processing into the PMOVES.AI ecosystem.

## Pipeline Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Trigger    │────▶│   ComfyUI   │────▶│   Render    │
│   (Agent/    │     │   Workflow   │     │   Webhook   │
│    NATS)     │     │   Execution  │     │  (port 8085)│
└─────────────┘     └──────┬──────┘     └──────┬──────┘
                           │                    │
                    ┌──────▼──────┐     ┌──────▼──────┐
                    │   Output    │     │  Supabase   │
                    │   MinIO     │     │  Metadata   │
                    │   (assets)  │     │  Record     │
                    └─────────────┘     └─────────────┘
```

## Workflow Types

### 1. Agent Card Art Generation

**Purpose:** Generate themed character art for PMOVES agents using ComfyUI.

**Trigger:** Skill pipeline `skills.pipeline.agent-card-gen.v1`

**Process:**
1. Theme lookup from `pmoves/configs/agent-themes.yaml`
2. Character spec assembly (traits, colors, style cues)
3. ComfyUI workflow execution with stable diffusion
4. Output stored to MinIO `assets/agent-cards/`
5. Supabase metadata record created
6. A2UI card component generated

**Themes Available:**
- Transformers 1986 (Optimus Prime, Megatron, Starscream, etc.)
- ThunderCats (Lion-O, Cheetara, Panthro, Mumm-Ra)
- Mega Man (Mega Man, Proto Man, Bass, Dr. Wily)
- Final Fantasy Tactics (Ramza, Agrias, Calculator, Mime)

### 2. Benchmark Comparison Visuals

**Purpose:** Generate "No PMOVES vs With PMOVES" comparison images.

**Trigger:** After `hf_benchmark_runner.py` completes

**Process:**
1. Benchmark data → A2UI chart spec
2. A2UI → Remotion renderer (Thread 2.1)
3. Remotion output → MinIO `assets/benchmarks/`

### 3. CHIT Constellation Art

**Purpose:** Artistic rendering of CHIT geometry patterns.

**Trigger:** Manual or via `hyperdim:render` skill

**Process:**
1. CGP packet data → parametric surface params
2. Three.js renderer or ComfyUI artistic interpretation
3. Output → MinIO + Open Notebook living page

## ComfyUI Integration

### Render Webhook (Port 8085)

The render webhook handles ComfyUI callback events:

```
POST http://localhost:8085/webhook/render
Headers:
  X-Webhook-Secret: ${RENDER_WEBHOOK_SHARED_SECRET}
Body:
  {
    "workflow_id": "agent-card-gen",
    "output_images": ["output_00001.png"],
    "prompt_id": "...",
    "metadata": {...}
  }
```

### Workflow Storage

ComfyUI workflows stored in PMOVES-Creator repository:
- `workflows/agent-card-gen.json` — Agent character art
- `workflows/benchmark-viz.json` — Performance comparison
- `workflows/constellation-art.json` — CHIT geometry art

## Data Flow

### Input Sources
- Agent theme registry (`agent-themes.yaml`)
- Benchmark results (`hf_benchmark_runner.py` output)
- CGP packets (`chit_encode_hook.py` output)
- User reference images (MinIO `assets/references/`)

### Output Destinations
- MinIO `assets/` bucket (images, videos)
- Supabase `pmoves_core` (metadata records)
- A2UI animation specs (for Remotion rendering)
- Open Notebook living pages (via notebook-sync)

## NATS Events

| Subject | Direction | Description |
|---------|-----------|-------------|
| `skills.pipeline.agent-card-gen.v1` | Consume | Trigger card generation |
| `ingest.file.added.v1` | Publish | New asset created |
| `a2ui.render.completed.v1` | Publish | Render job finished |

## Related Components

- **Render Webhook** (port 8085) — ComfyUI callback handler
- **MinIO** (port 9000) — Asset storage
- **Presign** (port 8088) — Signed URL generation
- **A2UI Renderer** (port 8105) — Remotion animation engine
- **Hyperdimensions** — Three.js parametric surfaces
