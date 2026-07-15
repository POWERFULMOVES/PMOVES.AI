---
name: kilocode-persona-grounding
description: Transform source materials into grounded persona anchors for PMOVES agents on the KiloCode GLM lane. Use when creating personas, grounding agent behavior, or establishing persona policy metadata.
keywords: [persona, grounding, anchor, archetype, agent-identity, kilocode, glm]
version: 1.0.0
category: PMOVES/KiloCode
---

# KiloCode Persona Grounding

Transform source materials into grounded persona anchors with policy metadata for PMOVES agents via KiloCode GLM inference.

## Purpose

Take source artifacts and approved ingest materials to create persona anchors that define agent identity, voice, and behavioral patterns for PMOVES agent operations. Route persona synthesis through TensorZero `coding_glm` / `coding_kilocode`.

## Capabilities

- 🎭 Define agent persona from source materials
- ⚓ Create grounding anchors for consistent behavior
- 📋 Generate persona policy metadata
- 🔗 Map source to anchor relationships
- 🤖 Leverage GLM-5-Turbo `architectural` voice for agent signatures

## Integration Points

- **Personas Table**: `pmoves_core.personas` in Supabase
- **Context Artifacts**: `pmoves/docs/context/`
- **Agent Registry**: `pmoves/config/agent_registry.yaml`
- **Agent Signatures**: `pmoves/config/agent_signatures.yaml`
- **TensorZero Functions**: `coding_glm`, `coding_kilocode`
- **NATS Subject**: `pmoves.persona.anchor.v1`

## Workflow

### 1. Source Material Analysis

```bash
# List available context artifacts
ls pmoves/docs/context/

# Read persona source materials
cat pmoves/docs/context/*persona*.md
```

### 2. Anchor Generation

Create persona anchor with:

```yaml
# .personas/<persona-name>/anchor.yaml
persona:
  name: <persona-name>
  archetype: <archetype-from-taxonomy>
  voice: architectural  # KiloCode-specific
  alter_ego: kilocode-glm
  
anchors:
  - type: behavioral
    trigger: "<situation pattern>"
    response: "<grounded response>"
    
policy_metadata:
  - key: tier
    value: 6  # Agent tier from taxonomy
  - key: evolution_path
    value: <from-taxonomy>
```

### 3. Supabase Insert

```sql
INSERT INTO pmoves_core.personas (name, version, metadata)
VALUES ('<persona-name>', '1.0.0', '<anchor_yaml>');
```

## Agent Taxonomy Alignment

Per `pmoves/docs/AGENTS/PMOVES_AGENT_CLASS_TAXONOMY.md`:

| Class | Tier | Persona Type |
|-------|------|--------------|
| Kinetic | 4 | ClawZ, Transformer |
| Archon | 6 | Knowledge, Muscles |
| DARKXSIDE | 7 | Strategic, Orchestration |

## KiloCode Voice Configuration

```yaml
voice:
  type: architectural  # KiloCode-specific
  alter: kilocode-glm
  resonance:
    - blueprint-first
    - mode-driven
    - vs-code-native
```

## Example Usage

```
User: "Create Archon persona anchor from context artifacts"

Agent:
1. Reads pmoves/docs/context/archon_sources/
2. Generates persona anchors with behavioral triggers via coding_glm
3. Maps to Agent Taxonomy tiers
4. Creates policy metadata
5. Inserts into Supabase personas table
```

## Trigger Phrases

- "create persona anchor"
- "ground agent identity"
- "persona grounding"
- "generate persona policy"
- "agent identity setup"
- "kilocode persona grounding"
