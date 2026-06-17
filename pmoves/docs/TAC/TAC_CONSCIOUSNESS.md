# TAC_CONSCIOUSNESS
_Last updated: 2026-03-15_

## Mission

Map consciousness topology via Compressed Geometric Packets (CGP). The Consciousness Service bridges the Tokenism Simulator and the Geometry Bus, encoding agent interactions, swarm dynamics, and attribution chains into CHIT-compatible geometric structures stored in Neo4j.

## Current State

- **Port:** 8106
- **Team:** Orchestration (agent-teams.yaml)
- **Dependencies:** Tokenism Simulator (8103), NATS (4222), Neo4j (7474/7687)
- **CHIT Integration:** Full target (5/5 toggles)
- **CGP Schema:** `chit.cgp.v1.0` (canonical), transported via `geometry.cgp.v1` NATS subject

## Architecture

```
  Agent Interactions        Swarm Dynamics
         │                       │
         ▼                       ▼
   Consciousness Service (8106)
         │
    ┌────┼────┐
    │    │    │
    ▼    ▼    ▼
  CGP   CHIT  Graph
 Encode Sign  Store
    │    │    │
    ▼    ▼    ▼
  geometry.cgp.v1 ──► Neo4j (7474)
         │
         ▼
  tokenism.cgp.ready.v1
         │
         ▼
  Tokenism Simulator (8103)
         │
         ▼
  tokenism.simulation.result.v1
```

## NATS Subjects

| Subject | Direction | Description |
|---------|-----------|-------------|
| `geometry.cgp.v1` | Publish | Compressed Geometric Packets |
| `tokenism.cgp.ready.v1` | Publish | CGP ready for simulation |
| `tokenism.simulation.result.v1` | Subscribe | Simulation results from Tokenism |
| `geometry.event.v1` | Publish | Consciousness lifecycle events |

## CGP Version Naming

| Context | Format | Example |
|---------|--------|---------|
| NATS transport | `geometry.cgp.v{N}` | `geometry.cgp.v1` |
| Payload spec | `chit.cgp.v{major}.{minor}` | `chit.cgp.v0.2` |
| Internal canonical | `chit.cgp.v{major}.{minor}` | `chit.cgp.v1.0` |

No conflict — the distinction is intentional (transport layer vs payload schema).

## Phases

1. **Encode** — Transform agent interactions into CGP geometry
2. **Sign** — CHIT HMAC signature for provenance (if `CHIT_PASSPHRASE` set)
3. **Store** — Persist to Neo4j knowledge graph
4. **Publish** — Emit to Geometry Bus via NATS
5. **Simulate** — Tokenism Simulator processes CGP for economic modeling
6. **Attribute** — Map simulation results back to consciousness topology

## Production Readiness

| Check | Status |
|-------|--------|
| NATS integration | Active (geometry bus) |
| Neo4j storage | Connected |
| CHIT toggles | Target: 5/5 |
| Auth | Network isolation |
| Docker Compose | Profile: `agents` |

## Verification

```bash
curl -s http://localhost:8106/healthz
nats sub "geometry.cgp.v1" --count=1
nats sub "tokenism.>" --count=1
```
