# PMOVES Persona Framework

**Version:** 1.1
**Last Updated:** 2026-03-01 (seed examples added)
**Status:** Phase 1 in progress — architecture defined, 8/12 core seeds deployed
**Seed SQL:** `pmoves/supabase/initdb/17_persona_seed.sql`

---

## Overview

The PMOVES Persona Framework defines a structured approach to creating, managing, and evolving AI agent personas. This document outlines the schema, mathematical foundations, and implementation roadmap for the referenced "325+ personas" across the CATACLYSM STUDIOS ecosystem.

---

## Persona Architecture

### Core Components

```
┌─────────────────────────────────────────────────────────────┐
│                    PERSONA FRAMEWORK                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │  Identity   │  │   Voice     │  │  Behavior   │         │
│  │   Layer     │  │   Layer     │  │   Layer     │         │
│  │             │  │             │  │             │         │
│  │ • Name      │  │ • TTS Model │  │ • Traits    │         │
│  │ • Avatar    │  │ • Pitch     │  │ • Style     │         │
│  │ • Backstory │  │ • Rate      │  │ • Boundaries│         │
│  │ • Domain    │  │ • Emotion   │  │ • Goals     │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
│           │              │              │                   │
│           └──────────────┼──────────────┘                   │
│                          ↓                                  │
│              ┌─────────────────────┐                        │
│              │   CHIT Attribution  │                        │
│              │   (Geometric Layer) │                        │
│              │                     │                        │
│              │ • Dirichlet Weights │                        │
│              │ • Hyperbolic Embed  │                        │
│              │ • Swarm Consensus   │                        │
│              └─────────────────────┘                        │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Database Schema

### `persona` Table

```sql
CREATE TABLE public.persona (
    id                       uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    slug                     text NOT NULL UNIQUE,
    name                     text NOT NULL,
    category                 text NOT NULL,

    -- Identity
    avatar_id                bigint REFERENCES public.persona_avatar(id),
    backstory                text,
    domain                   text[],  -- Areas of expertise

    -- Voice link
    voice_persona_id         uuid REFERENCES public.voice_persona(id),

    -- Behavior
    personality_traits       text[] DEFAULT '{}',
    communication_style      text DEFAULT 'professional',
    response_boundaries      jsonb DEFAULT '{}',
    goals                    text[],

    -- CHIT Integration
    chit_attribution_config  jsonb DEFAULT '{}',
    geometric_signature      vector(128),  -- Hyperbolic embedding

    -- Hierarchy
    parent_persona_id        uuid REFERENCES public.persona(id),
    inheritance_mode         text DEFAULT 'extend', -- extend | override | merge

    -- Status
    is_active                boolean NOT NULL DEFAULT true,
    created_at               timestamptz NOT NULL DEFAULT now(),
    updated_at               timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_persona_category ON public.persona(category);
CREATE INDEX idx_persona_geometric ON public.persona USING ivfflat (geometric_signature vector_cosine_ops);
```

### `persona_avatar` Table

```sql
CREATE TABLE public.persona_avatar (
    id                       bigserial PRIMARY KEY,
    persona_slug             text NOT NULL,
    avatar_type              text DEFAULT 'static', -- static | animated | 3d
    primary_image_uri        text,  -- MinIO: assets/avatars/{slug}.png
    thumbnail_uri            text,
    animation_config         jsonb DEFAULT '{}',
    created_at               timestamptz NOT NULL DEFAULT now()
);
```

---

## Persona Categories

The 325+ personas are organized into hierarchical categories:

### Category Breakdown

| Category | Count | Description |
|----------|-------|-------------|
| **Core Agents** | 12 | Primary orchestration personas |
| **Domain Experts** | 85 | Specialized knowledge areas |
| **Creative** | 45 | Art, music, writing personas |
| **Technical** | 65 | Engineering, DevOps, security |
| **Support** | 40 | Customer service, help desk |
| **Research** | 35 | Academic, scientific domains |
| **Entertainment** | 28 | Gaming, media, social |
| **Utility** | 15 | Tools, automation, data |

### Core Agent Personas

| Slug | Name | Role |
|------|------|------|
| `agent-zero` | Agent Zero | Central orchestrator |
| `archon` | Archon | Knowledge manager |
| `mesh-node` | Mesh Agent | Distributed coordinator |
| `flute-voice` | Flute | Voice communication |
| `supaserch` | SupaSerch | Deep research |
| `pmoves-crush` | PMOVES Crush | CLI companion |
| `deep-researcher` | DeepResearch | Research planner |
| `consciousness` | Consciousness | Self-awareness layer |

---

## Mathematical Foundations

### CHIT Attribution Config

Each persona has a CHIT configuration for geometric attribution:

```json
{
    "chit_attribution_config": {
        "dirichlet_alpha": [1.0, 1.0, 1.0],  // Prior distribution
        "hyperbolic_curvature": -1.0,         // Poincaré disk K
        "swarm_participation": true,          // EvoSwarm consensus
        "zeta_filter_enabled": true,          // Noise filtering
        "attribution_weight": 0.15            // Base contribution weight
    }
}
```

### Geometric Signature

Each persona has a 128-dimensional hyperbolic embedding for similarity search:

```python
# Generate geometric signature using hyperbolic-encoder
from chit import hyperbolic_encoder

signature = hyperbolic_encoder.embed_persona({
    "name": persona.name,
    "traits": persona.personality_traits,
    "domain": persona.domain,
    "backstory": persona.backstory
})

# Similarity search via pgvector
SELECT * FROM persona
WHERE geometric_signature <=> query_vector < 0.3
ORDER BY geometric_signature <=> query_vector
LIMIT 10;
```

### Dirichlet-Enhanced Attribution

When multiple personas contribute to a response, attribution uses Dirichlet distributions:

```python
from chit import dirichlet_weights

# Calculate contribution weights
contributions = {
    "agent-zero": 0.4,      # Primary orchestration
    "archon": 0.35,         # Knowledge retrieval
    "domain-expert": 0.25   # Specialized input
}

# Apply Dirichlet smoothing
weights = dirichlet_weights.compute(
    contributions,
    alpha=[1.2, 1.0, 0.8],  # Prior favoring orchestration
    temperature=0.5
)
```

---

## Persona Inheritance

Personas can inherit from parent personas:

### Inheritance Modes

| Mode | Behavior |
|------|----------|
| `extend` | Child adds to parent traits (default) |
| `override` | Child completely replaces parent traits |
| `merge` | Traits combined with deduplication |

### Example: Domain Expert Inheritance

```json
{
    "slug": "quantum-physicist",
    "parent_persona_id": "research-scientist",
    "inheritance_mode": "extend",
    "domain": ["quantum mechanics", "particle physics"],
    "personality_traits": ["analytical", "precise"]
}
```

Effective traits:
```
research-scientist traits: ["curious", "methodical", "patient"]
+ quantum-physicist traits: ["analytical", "precise"]
= ["curious", "methodical", "patient", "analytical", "precise"]
```

---

## Concrete Persona Seed Examples

The following personas are seeded in production via `pmoves/supabase/initdb/17_persona_seed.sql`. These serve as canonical examples of the schema in action.

### Example 1: Developer Persona

```yaml
-- From 17_persona_seed.sql
name: 'Developer'
version: '1.0'
thread_type: 'chained'           -- Sequential reasoning for code analysis
model_preference: 'claude-sonnet-4-5'  -- Balanced speed/quality
temperature: 0.3                 -- Focused, deterministic
max_tokens: 8192
behavior_weights: {"decode": 0.4, "retrieve": 0.3, "generate": 0.3}
tools_access: ["code_review", "git_operations", "terminal", "file_system", "search"]
```

**Why chained thread type?** Code review requires sequential reasoning — read the diff, understand context, identify issues, suggest fixes. Each step depends on the previous.

### Example 2: Researcher Persona

```yaml
name: 'Researcher'
version: '1.0'
thread_type: 'parallel'          -- Multi-threaded exploration
model_preference: 'claude-opus-4-5'   -- Maximum capability for deep analysis
temperature: 0.7                 -- Creative exploration
max_tokens: 16384
behavior_weights: {"decode": 0.3, "retrieve": 0.5, "generate": 0.2}
tools_access: ["search", "web_browse", "file_system", "knowledge_graph", "hirag_query"]
```

**Why parallel thread type?** Research benefits from exploring multiple angles simultaneously. The higher temperature encourages diverse exploration paths.

### Example 3: Security Auditor Persona

```yaml
name: 'Security Auditor'
version: '1.0'
thread_type: 'chained'
model_preference: 'claude-opus-4-5'   -- High capability for security analysis
temperature: 0.2                 -- Very focused, minimal hallucination
max_tokens: 8192
behavior_weights: {"decode": 0.5, "retrieve": 0.3, "generate": 0.2}
tools_access: ["code_review", "terminal", "file_system", "search", "security_scan"]
```

### Example 4: Archivist Persona (Cost-Optimized)

```yaml
name: 'Archivist'
version: '1.0'
thread_type: 'base'              -- Simple catalog operations
model_preference: 'claude-haiku-4-5'  -- Fast, cheap for routine tasks
temperature: 0.1                 -- Highly deterministic
max_tokens: 4096
behavior_weights: {"decode": 0.6, "retrieve": 0.3, "generate": 0.1}
tools_access: ["file_system", "search", "knowledge_graph"]
```

**Why Haiku?** Archival tasks (indexing, cataloging, metadata extraction) are routine and benefit more from speed/cost efficiency than reasoning depth.

### Inheritance Chain Example

```text
Coordinator (parent)
├── thread_type: 'big'
├── model_preference: 'claude-opus-4-5'
├── personality_traits: ["strategic", "organized", "decisive"]
│
└── Project Manager (child, extends Coordinator)
    ├── inheritance_mode: 'extend'
    ├── additional traits: ["detail-oriented", "deadline-aware"]
    ├── domain: ["project management", "sprint planning"]
    └── effective traits: ["strategic", "organized", "decisive",
                           "detail-oriented", "deadline-aware"]
```

### CHIT Attribution Config (Worked Example)

```json
{
    "chit_attribution_config": {
        "dirichlet_alpha": [1.2, 1.0, 0.8],
        "hyperbolic_curvature": -1.0,
        "swarm_participation": true,
        "zeta_filter_enabled": true,
        "attribution_weight": 0.35
    }
}
```

**Field meanings:**
- `dirichlet_alpha: [1.2, 1.0, 0.8]` — Prior favoring the first contributor (orchestrator gets slightly more credit)
- `hyperbolic_curvature: -1.0` — Standard Poincare disk curvature for similarity search
- `attribution_weight: 0.35` — This persona contributes ~35% base weight in multi-persona responses
- `swarm_participation: true` — Participates in EvoSwarm consensus rounds

### All 8 Seeded Personas

| Name | Thread Type | Model | Temperature | Key Behavior |
|------|-------------|-------|-------------|--------------|
| Developer | chained | claude-sonnet-4-5 | 0.3 | Code-focused, sequential |
| Creator | parallel | claude-sonnet-4-5 | 0.8 | Creative, multi-path |
| Researcher | parallel | claude-opus-4-5 | 0.7 | Deep analysis, exploration |
| Analyst | fusion | claude-sonnet-4-5 | 0.4 | Multi-source synthesis |
| Coordinator | big | claude-opus-4-5 | 0.5 | Orchestration, delegation |
| Security Auditor | chained | claude-opus-4-5 | 0.2 | Strict, deterministic |
| Tester | chained | claude-sonnet-4-5 | 0.3 | Test generation, validation |
| Archivist | base | claude-haiku-4-5 | 0.1 | Cataloging, fast/cheap |

**Source:** `pmoves/supabase/initdb/17_persona_seed.sql`

---

## Communication Styles

| Style | Description | Use Case |
|-------|-------------|----------|
| `professional` | Formal, clear, concise | Business, technical |
| `friendly` | Warm, approachable | Customer support |
| `academic` | Precise, referenced | Research, education |
| `casual` | Relaxed, conversational | Entertainment |
| `authoritative` | Confident, decisive | Leadership roles |
| `creative` | Expressive, imaginative | Art, writing |
| `technical` | Detailed, specific | Engineering |
| `supportive` | Empathetic, helpful | Wellness, coaching |

---

## Response Boundaries

JSON configuration for persona behavior limits:

```json
{
    "response_boundaries": {
        "max_response_length": 500,
        "forbidden_topics": ["politics", "religion"],
        "requires_sources": true,
        "confidence_threshold": 0.7,
        "escalation_triggers": ["legal", "medical", "financial"],
        "handoff_persona": "human-support",
        "tone_restrictions": ["aggressive", "sarcastic"]
    }
}
```

---

## Implementation Roadmap

### Phase 1: Core Personas (Q1 2026) (In Progress)
- [ ] Define 12 core agent personas (8/12 seeded in production)
- [ ] Implement persona schema in Supabase
- [ ] Link to existing voice personas
- [ ] Basic CHIT attribution integration

### Phase 2: Domain Expansion (Q2 2026)
- [ ] Add 85 domain expert personas
- [ ] Implement inheritance system
- [ ] Geometric signature generation
- [ ] Similarity search via pgvector

### Phase 3: Full Catalog (Q3 2026)
- [ ] Complete 325+ persona catalog
- [ ] Advanced Dirichlet attribution
- [ ] Swarm consensus for multi-persona responses
- [ ] Avatar generation pipeline

### Phase 4: Evolution (Q4 2026)
- [ ] Persona learning from interactions
- [ ] Dynamic trait adjustment
- [ ] User-created personas
- [ ] Consciousness service integration

---

## API Endpoints

### List Personas

```
GET /v1/personas
Query: ?category=core&active=true&limit=50
Response: {
    "personas": [...],
    "total": 325,
    "categories": {...}
}
```

### Get Persona

```
GET /v1/personas/{slug}
Response: {
    "id": "uuid",
    "slug": "agent-zero",
    "name": "Agent Zero",
    "category": "core",
    "personality_traits": [...],
    "voice_persona": {...},
    "chit_attribution_config": {...}
}
```

### Find Similar Personas

```
POST /v1/personas/similar
Request: {
    "query": "need a friendly expert in quantum physics",
    "limit": 5
}
Response: {
    "personas": [
        {"slug": "quantum-physicist", "similarity": 0.92},
        {"slug": "physics-tutor", "similarity": 0.85}
    ]
}
```

### Create Persona

```
POST /v1/personas
Request: {
    "slug": "my-custom-persona",
    "name": "Custom Expert",
    "category": "domain-expert",
    "parent_persona_id": "research-scientist",
    ...
}
```

---

## NATS Events

```
persona.created.v1
  Payload: { persona_id, slug, category }

persona.updated.v1
  Payload: { persona_id, changes }

persona.activated.v1
  Payload: { persona_id, agent_id }

persona.attributed.v1
  Payload: { persona_ids[], weights[], cgp_packet_id }
```

---

## Storage

### Avatars

```
MinIO: assets/avatars/{persona_slug}/
├── primary.png       # 512x512 main avatar
├── thumbnail.png     # 128x128 thumbnail
├── animated.gif      # Optional animation
└── 3d-model.glb      # Optional 3D avatar
```

### Geometric Signatures

Stored as:
- `geometric_signature` column (vector(128))
- Indexed via pgvector IVFFlat for similarity search
- Generated by hyperbolic-encoder on creation/update

---

## Integration Points

### With Voice Personas
```
persona.voice_persona_id → voice_persona.id
```

### With CHIT Attribution
```
persona.chit_attribution_config → CGP packets
persona.geometric_signature → Shape Store queries
```

### With Consciousness Service
```
consciousness-service uses persona.personality_traits
to modulate response generation
```

### With Agent Zero
```
agent-zero.persona_routing determines which
persona handles each user request
```

---

## Related Documentation

- `.claude/context/voice-personas.md` - Voice persona system
- `pmoves/docs/FLUTE_PROSODIC_ARCHITECTURE.md` - Voice synthesis
- `pmoves/docs/PMOVESCHIT/IMPLEMENTATION_STATUS.md` - CHIT status
- `CATACLYSM_STUDIOS_INC/ABOUT/` - Brand and platform vision
