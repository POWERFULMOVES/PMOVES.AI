---
name: minimax-persona-grounding
description: Transform source materials into grounded persona anchors for PMOVES agents. This skill should be used when creating personas, grounding agent behavior, or establishing persona policy metadata.
keywords: [persona, grounding, anchor, archetype, agent-identity]
version: 1.0.0
category: PMOVES/MiniMax
---

# MiniMax Persona Grounding

Transform source materials into grounded persona anchors with policy metadata for PMOVES agents.

## Purpose

Take source artifacts and approved ingest materials to create persona anchors that define agent identity, voice, and behavioral patterns for PMOVES agent operations.

## Capabilities

- 🎭 Define agent persona from source materials
- ⚓ Create grounding anchors for consistent behavior
- 📋 Generate persona policy metadata
- 🔗 Map source to anchor relationships
- ✨ Leverage MiniMax `dimensional` voice for agent signatures

## Integration Points

- **Personas Table**: `pmoves_core.personas` in Supabase
- **Context Artifacts**: `pmoves/docs/context/`
- **Agent Registry**: `pmoves/config/agent_registry.yaml`
- **Agent Signatures**: `pmoves/config/agent_signatures.yaml`
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
  voice: dimensional  # MiniMax-specific
  alter_ego: minimax-ghost
  
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

## MiniMax Voice Configuration

```yaml
voice:
  type: dimensional  # MiniMax-specific
  alter: minimax-ghost
  resonance:
    - native-model
    - hyperdimensional-ops
```

## Example Usage

```
User: "Create Archon persona anchor from context artifacts"

Agent:
1. Reads pmoves/docs/context/archon_sources/
2. Generates persona anchors with behavioral triggers
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
