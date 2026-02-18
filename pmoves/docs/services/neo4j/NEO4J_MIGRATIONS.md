# PMOVES.AI Neo4j Migrations Guide

**Complete guide for Neo4j graph database migrations in PMOVES.AI**

## Table of Contents

1. [Overview](#overview)
2. [CHIT Mind Map Structure](#chit-mind-map-structure)
3. [Migration Files](#migration-files)
4. [Running Migrations](#running-migrations)
5. [Data Model](#data-model)
6. [Troubleshooting](#troubleshooting)

---

## Overview

PMOVES.AI uses Neo4j for the knowledge graph that powers:
- **CHIT (Compressed Hierarchical Information Transfer)** - Encoded data representations
- **Mind Maps** - Concept relationships and associations
- **Entity Graph** - Person aliases and cross-references

### Migration Location

```
pmoves/neo4j/cypher/
├── 001_init.cypher                    # Constraints and indexes
├── 002_load_person_aliases.cypher     # Person alias mappings
├── 003_seed_chit_mindmap.cypher       # CHIT demo constellation
├── 010_chit_geometry_fixture.cypher    # CHIT geometry test data
└── 011_chit_geometry_smoke.cypher     # Smoke test data
```

---

## CHIT Mind Map Structure

The CHIT (Compressed Hierarchical Information Transfer) mind map represents encoded multi-modal data as a graph.

### Graph Nodes

| Node Type | Label | Properties | Purpose |
|-----------|-------|------------|---------|
| **Anchor** | `:Anchor` | `id`, `model`, `dim`, `label`, `modality`, `anchor` (float4[]) | CHIT encoded vector anchor |
| **Constellation** | `:Constellation` | `id`, `spectrum`, `radial_min`, `radial_max`, `bins`, `summary` | Cluster of related points |
| **Point** | `:Point` | `id`, `source_ref`, `proj`, `conf`, `x`, `y`, `modality`, `text` | Individual data points |
| **MediaRef** | `:MediaRef` | `uid`, `modality`, `ref_id`, `token_start/end`, `t_start/end`, `frame_idx` | Source media references |
| **Entity** | `:Entity` | `value` (unique) | Generic entities (person aliases, etc.) |

### Graph Relationships

| Relationship | From → To | Purpose |
|--------------|-----------|---------|
| `:FORMS` | Anchor → Constellation | Anchor forms a constellation |
| `:HAS` | Constellation → Point | Constellation contains points |
| `:LOCATES` | Point → MediaRef | Point references source media |

### Example CHIT Graph

```
Anchor (sports/basketball video)
  └─FORMS→ Constellation (Basketball practice timeline)
            ├─HAS→ Point (doc:codebook#t1) ──LOCATES→ MediaRef (doc|codebook|0-6)
            ├─HAS→ Point (doc:codebook#t8) ──LOCATES→ MediaRef (doc|codebook|7-12)
            └─HAS→ Point (yt_dQw4w9WgXcQ#37.2-39.7) ──LOCATES→ MediaRef (video|yt|37.2-39.7)
```

---

## Migration Files

### 001_init.cypher

**Purpose:** Initialize graph constraints

```cypher
CREATE CONSTRAINT entity_value_unique IF NOT EXISTS FOR (e:Entity) REQUIRE e.value IS UNIQUE;
```

Creates unique constraint on Entity values for data integrity.

### 002_load_person_aliases.cypher

**Purpose:** Load person alias mappings for entity resolution

Creates `:Entity` nodes with person names and their aliases for cross-reference in knowledge graphs.

### 003_seed_chit_mindmap.cypher

**Purpose:** Seed sample CHIT constellation for local testing

**Data Seeded:**
- **Anchor:** `6d8d2e65-b6b9-4d3a-9b5e-3a9c42c1b111` (mini-vec-4d, sports/basketball)
- **Constellation:** `8c1b7a8c-7b38-4a6b-9bc3-3f1fdc9a1111` (Basketball-ish topics)
- **Points:** 3 points (2 text, 1 video)
- **MediaRefs:** 3 media references (2 doc, 1 video)

### 010_chit_geometry_fixture.cypher

**Purpose:** Idempotent CHIT geometry fixture for testing

Same data structure as `003_seed_chit_mindmap.cypher` but written for idempotent re-running.

### 011_chit_geometry_smoke.cypher

**Purpose:** Smoke test data for CHIT geometry validation

Minimal dataset for testing CHIT encoding/decoding pipelines.

---

## Running Migrations

### Method 1: Direct Cypher Execution

```bash
# Connect to Neo4j
docker exec -it pmoves-neo4j-1 cypher-shell -u neo4j -p ${NEO4J_PASSWORD}

# Execute migration file
cat pmoves/neo4j/cypher/001_init.cypher | cypher-shell -u neo4j -p ${NEO4J_PASSWORD}
```

### Method 2: Using make Command

```bash
cd pmoves
make neo4j-bootstrap
```

### Method 3: Via Scripts

```bash
# Apply all migrations
./scripts/apply_migrations_docker.sh
```

### Verify Migration Status

```cypher
// Check if constraint exists
SHOW CONSTRAINTS;

// Count nodes by type
MATCH (n:Anchor) RETURN count(*) as anchors;
MATCH (n:Constellation) RETURN count(*) as constellations;
MATCH (n:Point) RETURN count(*) as points;
MATCH (n:MediaRef) RETURN count(*) as media_refs;
MATCH (n:Entity) RETURN count(*) as entities;

// Check relationships
MATCH ()-[r]->() RETURN type(r), count(*) as count ORDER BY count DESC;
```

---

## Data Model

### Anchor Node

Represents a CHIT encoded vector anchor (compressed data representation).

```cypher
:Anchor {
  id: "uuid",
  model: "mini-vec-4d",
  dim: 4,
  label: "sports/basketball",
  modality: "text|video|audio|image|latent",
  anchor: [0.8, 0.2, 0.0, 0.0]
}
```

### Constellation Node

Groups related points into a cluster.

```cypher
:Constellation {
  id: "uuid",
  spectrum: [0.05, 0.15, 0.30, 0.30, 0.20],
  radial_min: 0.0,
  radial_max: 1.0,
  bins: 5,
  summary: "Basketball practice timeline"
}
```

### Point Node

Individual data point with projection and confidence.

```cypher
:Point {
  id: "uuid",
  source_ref: "doc:codebook#t1",
  proj: 0.95,
  conf: 0.92,
  x: 0.1,
  y: 0.2,
  modality: "text",
  text: "Basketball practice and drills"
}
```

### MediaRef Node

References the source media for a point.

```cypher
:MediaRef {
  uid: "doc|codebook|0-6",
  modality: "doc",
  ref_id: "codebook",
  token_start: 0,
  token_end: 6
}

// Video reference
:MediaRef {
  uid: "video|yt_dQw4w9WgXcQ|37.2-39.7",
  modality: "video",
  ref_id: "yt_dQw4w9WgXcQ",
  t_start: 37.2,
  t_end: 39.7,
  frame_idx: 1112,
  scene: "free throws"
}
```

### Entity Node

Generic entity for person aliases and cross-references.

```cypher
:Entity {
  value: "John Doe"  // Must be unique
}
```

---

## PostgreSQL ↔ Neo4j Sync

Some CHIT data exists in both PostgreSQL and Neo4j for different access patterns:

| Data | PostgreSQL (via PostgREST) | Neo4j (via Cypher) |
|------|---------------------------|-------------------|
| Anchors | `public.anchors` | `:Anchor` nodes |
| Constellations | `public.constellations` | `:Constellation` nodes |
| Shape Points | `public.shape_points` | `:Point` nodes |
| Shape Index | `public.shape_index` | `:Point` + `:MediaRef` |
| Person Aliases | N/A | `:Entity` nodes |

**Use PostgreSQL when:**
- Need SQL joins with other tables
- Using PostgREST API
- Need pagination/filtering

**Use Neo4j when:**
- Traversing relationships
- Finding shortest paths
- Multi-hop graph queries

---

## Troubleshooting

### Constraint Already Exists

**Symptom:** `Equivalent constraints already exist`

**Cause:** Migration already applied.

**Fix:** Use `IF NOT EXISTS` in migrations (already done in `001_init.cypher`).

### Duplicate Nodes

**Symptom:** Multiple nodes with same ID after re-running migration.

**Fix:** Use `MERGE` instead of `CREATE` for idempotent migrations.

```cypher
// ❌ WRONG - creates duplicates
CREATE (a:Anchor {id: 'xxx'})

// ✅ CORRECT - idempotent
MERGE (a:Anchor {id: 'xxx'})
SET a.model = 'mini-vec-4d'
```

### Connection Refused

**Symptom:** `Failed to connect to Neo4j`

**Fix:**
```bash
# Check Neo4j is running
docker ps | grep neo4j

# Check password
echo $NEO4J_PASSWORD

# Check connection
docker exec pmoves-neo4j-1 cypher-shell -u neo4j -p ${NEO4J_PASSWORD} "RETURN 1"
```

### Memory Issues

**Symptom:** `OutOfMemoryError` during large graph operations.

**Fix:** Increase Neo4j heap size in docker-compose.yml:
```yaml
neo4j:
  environment:
    - NEO4J_dbms_memory_heap_initial__size=512m
    - NEO4J_dbms_memory_heap_max__size=512m
```

---

## See Also

- **[SUPABASE_MIGRATIONS.md](SUPABASE_MIGRATIONS.md)** - PostgreSQL migrations
- **[docs/pmoves_chit_all_in_one/](../pmoves_chit_all_in_one/)** - CHIT documentation
- **[PORT_REGISTRY.md](PORT_REGISTRY.md)** - Neo4j ports (7474 HTTP, 7687 Bolt)
