---
name: minimax-cgp-generate
description: Generate CGP (Creative Gamespace Packet) content for PMOVES creator workflows. This skill should be used when generating CGP packets, creating creative content, or executing creator demos.
keywords: [cgp, creative, gamespace, packet, creator, content-generation]
version: 1.0.0
category: PMOVES/MiniMax
---

# MiniMax CGP Generate

Generate CGP (Creative Gamespace Packet) content for PMOVES creator workflows with MiniMax inference.

## Purpose

Generate CGP packets that package creative content for PMOVES creator workflows. CGPs encapsulate media, metadata, and context for ingestion into Jellyfin, Invidious, and other content systems.

## Capabilities

- 📦 Generate CGP packet structure
- 🎨 Creative content synthesis
- 🏷️ Metadata injection
- 🔗 Multi-modal binding (video/audio/text)
- ⚡ Fast generation via MiniMax

## Integration Points

- **PMOVES-Creator**: Creator workflow engine
- **Jellyfin**: Media library integration
- **Invidious**: YouTube fallback
- **TensorZero**: Routes through `localhost:3030`
- **NATS Subject**: `pmoves.creator.cgp.v1`

## CGP Packet Structure

```yaml
# CGP v1 packet
cgp:
  version: "1.0"
  type: <health|finance|vibe>
  timestamp: <ISO8601>
  
  content:
    title: <string>
    description: <string>
    media:
      - type: video|audio|image
        url: <string>
        format: <string>
    transcript: <string>
    
  metadata:
    tags: [<string>]
    category: <string>
    source: <string>
    
  context:
    agent_id: <string>
    run_id: <string>
    parent_cgp: <uuid>
```

## Workflow

### 1. Define CGP Parameters

```bash
# Generate CGP from prompt
./scripts/cgp-generate.py \
  --type health \
  --prompt "Morning workout routine" \
  --format video
```

### 2. Inject Metadata

```bash
# Add metadata to CGP
./scripts/cgp-inject-metadata.py \
  --cgp-id <uuid> \
  --tags ["fitness", "morning"] \
  --category workout
```

### 3. Publish CGP

```bash
# Publish to NATS
nats pub pmoves.creator.cgp.v1 <cgp_json>
```

## Demo Commands

Per `docs/MAKE_TARGETS.md`:

```bash
# Health CGP demo
make demo-health-cgp

# Finance CGP demo
make demo-finance-cgp
```

## CGP Types

| Type | Description | Use Case |
|------|-------------|----------|
| health | Health/fitness content | Workout routines |
| finance | Finance/business content | Market analysis |
| vibe | Creative/artistic content | Mood boards |
| knowledge | Educational content | Learning modules |

## Example Usage

```
User: "Generate health CGP for morning workout"

Agent:
1. Creates CGP packet structure
2. Generates content via MiniMax
3. Binds video/audio assets
4. Injects metadata and tags
5. Publishes to NATS
6. Returns CGP ID
```

## Trigger Phrases

- "generate CGP"
- "create gamespace packet"
- "creative content generation"
- "CGP demo"
- "bind media to CGP"
