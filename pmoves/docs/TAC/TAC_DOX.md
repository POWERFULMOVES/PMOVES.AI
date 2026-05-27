# TAC Tree: DoX

> Technology-Architecture-Context tree for the DoX document intelligence and geometric visualization service.

## Service Identity

| Field | Value |
|-------|-------|
| **Service** | DoX |
| **Port** | TBD (no HTTP port assigned yet) |
| **Health** | `GET /healthz` (planned) |
| **Submodule** | `PMOVES-DoX` |
| **Docker Profile** | `workers` |
| **Tier** | worker |
| **Class** | Standard |
| **Evolution** | Stage 1 |

## Upstream Dependencies

| Dependency | Type | Required |
|------------|------|----------|
| NATS (4222) | Event-driven document processing | Yes |
| MinIO (9000) | Document storage | Yes |
| Supabase PostgREST (3010) | Document metadata | Yes |
| Agent Zero (8080) | Orchestration | Yes |

## Downstream Consumers

| Consumer | Interface | Description |
|----------|-----------|-------------|
| Extract Worker | NATS events | Document text for embedding |
| Hi-RAG v2 | Via indexed content | Retrieval queries |
| Hyperdimensions | WebSocket | Geometry Bus visualization |
| ToKenism | CGP packets | CHIT attribution for document processing |

## Key Capabilities

| Capability | Description |
|------------|-------------|
| Geometric Intelligence | Deterministic embedding-to-Poincare projection plus Hyperbolic/Manifold3D/Zeta (heuristic) visualization |
| CHIT Geometry Bus | WebSocket-based shape-encoded transport |
| Path Traversal Defense | Excellent — validated in Phase C audit |
| Fail-closed JWT | Properly implemented authentication |

## NATS Subjects

| Subject | Direction | Description |
|---------|-----------|-------------|
| (none declared) | — | No NATS subjects currently registered |

**Planned subjects:**
- `dox.document.processed.v1` — Document processing complete
- `dox.geometry.visualization.v1` — Geometry visualization request

## CHIT Integration Status

| Capability | Status | Notes |
|------------|--------|-------|
| Delta sensitivity | Yes | `chit_toggles.delta_sensitive: true` |
| Hz sensitivity | Yes | `chit_toggles.hz_sensitive: true` |
| CGP packet generation | Planned | Not yet publishing |
| Geometry Bus client | Active | WebSocket to Hyperdimensions |
| Hyperbolic embedding projection | Active | `GeometryEngine.project_embeddings_to_poincare`; exposed on cipher and A2A geometry responses |
| BPM capable | No | Document-oriented, not prosodic |

## Production Audit Checklist

| Requirement | Status | Notes |
|-------------|--------|-------|
| `/healthz` endpoint | Partial | Planned but no HTTP port assigned |
| `/metrics` (Prometheus) | Partial | Not exposed yet |
| Auth (JWT/Bearer) | **GREEN** | Fail-closed JWT — properly implemented |
| Docker hardening | Yes | Standard hardening patterns |
| NATS auth | **P1** | NATS completely unauthenticated — no auth block in `nats.conf` |
| `env.shared` format | OK | No `export` syntax issues |
| Path traversal | **GREEN** | Excellent defense — validated |

## Security Stance (Phase C Audit)

| Finding | Severity | Status |
|---------|----------|--------|
| NATS completely unauthenticated | P1 | **Open** — no auth block in `nats.conf` |
| Path traversal defense | GREEN | Excellent |
| Fail-closed JWT | GREEN | Properly implemented |

## Geometry Bus Integration

DoX serves as the **geometric intelligence** layer:

```
Document Input → DoX Processing → Geometry Encoding
                     ↓
              Poincare Projection
                     ↓
              Manifold3D Visualization
                     ↓
              Zeta-like Spectral View (heuristic)
                     ↓
              CHIT Geometry Bus (WebSocket)
                     ↓
              Hyperdimensions (3D Viz)
```

## Cross-Links

- **Submodule:** `PMOVES-DoX/`
- **Geometry Bus:** `.claude/context/geometry-nats-subjects.md`
- **Integration Topology:** [`TAC_INTEGRATION_TOPOLOGY.md`](./TAC_INTEGRATION_TOPOLOGY.md)
- **Agent Registry:** `pmoves/config/agent_registry.yaml` → `dox`
- **Audit Details:** `docs/submodules-audit-final-summary.md` → DoX section
- **CHIT Math:** `pmoves/docs/PMOVESCHIT/Integrating Math into PMOVES.AI.md`

## Open Items

- NATS auth block entirely missing from `nats.conf`
- HTTP port assignment needed for `/healthz` and `/metrics`
- NATS subject declarations needed in agent registry
- LONGBOW/Arrow bridge still needed for vector storage and retrieval handoff
- Branch divergence required reset pattern (>100 commits)

<!-- GRAPHITI_MARK: CLAUDE-OPUS::TAC-TOPOLOGY-AUDIT::2026-02-20 -->
