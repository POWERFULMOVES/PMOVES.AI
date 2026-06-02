# consciousness-service — Topology Bridge

Maps consciousness topology via Compressed Geometric Packets (CGP). Bridges the Tokenism Simulator and the Geometry Bus, encoding agent interactions, swarm dynamics, and attribution chains into CHIT-compatible geometric structures stored in Neo4j.

> **Canonical TAC reference**: `pmoves/docs/TAC/TAC_CONSCIOUSNESS.md` (richer architectural treatment; this README is the operator quick-reference).

## Quick reference

- **Port**: `:8105`
- **Health**: `GET /healthz`
- **Team**: Orchestration (`pmoves/configs/agent-teams.yaml`)
- **Dependencies**: Tokenism Simulator (`:8103`), NATS (`:4222`), Neo4j (`:7474` HTTP / `:7687` Bolt)
- **CHIT integration**: **Full** target (5/5 toggles per `pmoves/docs/audit/CHIT_INTEGRATION_STATUS.md`)
- **CGP schema**: `chit.cgp.v1.0` (payload canonical), transported via `geometry.cgp.v1` NATS subject

## Architecture (condensed)

```
   Agent Interactions ──┐
                        ▼
                 Consciousness Service (8105)
                        │
                   ┌────┼────┐
                   ▼    ▼    ▼
                  CGP  CHIT  Graph
                Encode Sign  Store
                   │    │    │
                   └─┬──┴────┴─► Neo4j (7474)
                     ▼
              geometry.cgp.v1 ──► Tokenism Simulator (8103)
                                       │
                                       ▼
                          tokenism.cgp.ready.v1
                          tokenism.simulation.result.v1
```

## NATS subjects

| Subject | Direction | Description |
|---------|-----------|-------------|
| `geometry.cgp.v1` | Publish | Compressed Geometric Packets |
| `tokenism.cgp.ready.v1` | Publish | CGP ready for simulation |
| `tokenism.simulation.result.v1` | Subscribe | Simulation results |
| `geometry.event.v1` | Publish | Consciousness lifecycle events |

## CGP version naming

| Context | Format | Example |
|---------|--------|---------|
| NATS transport | `geometry.cgp.v{N}` | `geometry.cgp.v1` |
| Payload spec | `chit.cgp.v{major}.{minor}` | `chit.cgp.v1.0` |
| Internal canonical | `chit.cgp.v{major}.{minor}` | `chit.cgp.v1.0` |

(Transport ≠ payload schema. Don't conflate.)

## Bringup

```bash
make -C pmoves up-consciousness   # or via bringup-layered for full mesh
```

## Cross-references

- TAC tree (canonical): `pmoves/docs/TAC/TAC_CONSCIOUSNESS.md`.
- Tokenism: `pmoves/services/tokenism-simulator/`.
- CHIT integration status: `pmoves/docs/audit/CHIT_INTEGRATION_STATUS.md`.
- Patterns: `.claude/PATTERNS.md` § CHIT.
