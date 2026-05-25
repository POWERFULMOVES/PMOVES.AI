# TAC Tree: ToKenism-Multi

> Technology-Architecture-Context tree for the ToKenism economic simulation and CHIT attribution engine.

**Last reviewed:** 2026-05-22 against `PMOVES-ToKenism-Multi/integrations/contracts/chit/` and the PMOVES tokenism-simulator service.

## Service Identity

| Field | Value |
|-------|-------|
| **Service** | ToKenism-Multi |
| **Port** | None (library + smart contracts) |
| **Health** | N/A (no HTTP service) |
| **Submodule** | `PMOVES-ToKenism-Multi` |
| **Docker Profile** | N/A |
| **Tier** | worker (economic simulation) |
| **Class** | Standard |
| **Evolution** | Base |

## Architecture

ToKenism is not a standalone service — it is a **CHIT attribution engine** comprising:

1. **CHIT TypeScript modules** (`integrations/contracts/chit/`)
   - `dirichlet-weights.ts` — Dirichlet-weighted contribution scoring
   - `shape-attribution.ts` — action records plus SHA-256 / keccak256 Merkle proof verification
   - `hyperbolic-encoder.ts` — Poincare disk embedding support
   - `cgp-generator.ts` — deterministic CGP document generation
   - `swarm-attribution.ts` — bounded fitness and population metadata tracking
   - `zeta-filter.ts` — zeta-zero-weighted heuristic spectral transform
   - `chit-nats-publisher.ts` — schema-validated NATS publishing
   - `index.ts` — factory, exports, and default subject constants

2. **Smart contracts** (Hardhat/Solidity)
   - FoodUSD, GroToken, GroupPurchase, CoopGovernor, RewardsPool

3. **Finance event simulation**
   - Economic modeling with Gini coefficient and poverty rate tracking

## Upstream Dependencies

| Dependency | Type | Required |
|------------|------|----------|
| NATS (4222) | Event publishing for attribution | Yes |
| Supabase (3010) | Attribution records storage | Yes |
| Ethereum RPC | Smart contract deployment | Optional (testnet) |

## Downstream Consumers

| Consumer | Interface | Description |
|----------|-----------|-------------|
| Hi-RAG v2 | `tokenism.cgp.ready.v1` | CGP packet indexing |
| Publisher-Discord | `tokenism.*` | Discord notification embeds |
| Hyperdimensions | `geometry.visualization.request.v1` | Visualization of attribution geometry |
| Flute Gateway | `tokenism.prosodic.bpm.v1` | BPM-encoded prosodic events (consumer) |
| Swarm Attribution | `geometry.attribution.request.v1` | Shape-attribution consensus |

## NATS Subjects

| Subject | Direction | Description |
|---------|-----------|-------------|
| `tokenism.cgp.weekly.v1` | Publishes | Weekly CGP economic simulation report |
| `tokenism.attribution.recorded.v1` | Publishes | Real-time attribution action recorded |
| `tokenism.cgp.ready.v1` | Publishes | Generic CGP packet ready for consumption |
| `tokenism.swarm.population.v1` | Publishes | Swarm fitness/population metadata update |
| `tokenism.settlement.requested.v1` | Publishes | Signed settlement batch planned from CGP attribution |
| `tokenism.settlement.recorded.v1` | Publishes | Settlement instruction recorded or idempotently skipped |
| `tokenism.settlement.failed.v1` | Publishes | Settlement instruction failure with retry metadata |
| `tokenism.geometry.event.v1` | Consumed from Flute | Legacy direct voice geometry event; still used by services but not one of the hardened ToKenism publisher schemas |
| `tokenism.prosodic.bpm.v1` | Consumed from Flute | BPM-encoded prosodic timeline event outside the ToKenism CHIT module |

## CHIT Integration Status

ToKenism **is** the CHIT engine — all CHIT integration radiates from here.

| Capability | Status | Notes |
|------------|--------|-------|
| CGP v0.2/v1.0 generation | Active | `cgp-generator.ts`; schemas accept both current compatibility specs |
| Dirichlet weighting | Active | `dirichlet-weights.ts` |
| Merkle verification | Active | `shape-attribution.ts`; real SHA-256 and keccak256, order-preserving proof paths |
| Hyperbolic embedding | Partial | `hyperbolic-encoder.ts`; embedding support, not a proof-backed fairness layer |
| Swarm metadata | Active | `swarm-attribution.ts`; records bounded fitness and population summaries only |
| Zeta spectral filtering | Heuristic | `zeta-filter.ts`; method design still required before stronger claims |
| BPM/prosodic mapping | External | Implemented in PMOVES voice/prosodic tools, not a ToKenism CHIT module |
| Smart contract attribution | Firefly approval-gated settlement interface | Contract models, settlement schemas, Firefly transaction drafts, live Firefly approval gate, and schema-validated result publishing exist; chain execution remains gated |

## Production Audit Checklist

| Requirement | Status | Notes |
|-------------|--------|-------|
| `/healthz` endpoint | N/A | Library, not service |
| `/metrics` (Prometheus) | N/A | Library has no endpoint; Flask simulator has service metrics |
| Auth (JWT/Bearer) | Partial | Smart contract auth only |
| Docker hardening | Yes | Standard patterns applied |
| NATS auth | Yes | Uses authenticated NATS |
| `env.shared` format | Resolved | Docker-compatible `KEY=value` syntax in `PMOVES-ToKenism-Multi/env.shared` |
| Hardhat CI | Open | Verify dependencies and working directory before contract test expansion |
| Temp files | Unknown | Re-audit before treating old temp-file count as current |
| Duplicate layout | Unknown | Re-audit before treating old duplicate-layout count as current |

## Security Stance

| Finding | Severity | Status |
|---------|----------|--------|
| `export` syntax in `env.shared` | P1 | **Resolved** — no `export` prefix in `PMOVES-ToKenism-Multi/env.shared` |
| NATS_URL missing credentials | P1 | **Resolved** — defaults to `nats://nats:pmoves@nats:4222` |
| Hardhat CI / local contract test coverage | P2 | **Open** |
| Old temp-file and duplicate-layout findings | P3 | Re-audit required; do not reuse stale counts without verification |

## Prosodic Integration

The old ToKenism TAC referenced a `musicMapping.ts` module, but that file is not part of the current CHIT TypeScript module set. BPM/prosodic encoding now lives in PMOVES voice/prosodic services and tools, with Tokenism consuming or publishing compatible NATS events where required.

Current relevant subjects:
- `tokenism.geometry.event.v1` for legacy/direct voice geometry events.
- `tokenism.prosodic.bpm.v1` for BPM-encoded prosodic timelines.
- `geometry.cgp.v1` for canonical geometry CGP traffic.

## Cross-Links

- **Submodule:** `PMOVES-ToKenism-Multi/`
- **CHIT Modules:** `PMOVES-ToKenism-Multi/integrations/contracts/chit/`
- **GEOMETRY BUS:** `.claude/context/geometry-nats-subjects.md`
- **BPM Math:** `pmoves/docs/AGENTS/AGNOTE4482.BEATS.md`
- **Flute Prosodics:** [`pmoves/docs/FLUTE_PROSODIC_ARCHITECTURE.md`](../FLUTE_PROSODIC_ARCHITECTURE.md)
- **Integration Topology:** [`TAC_INTEGRATION_TOPOLOGY.md`](./TAC_INTEGRATION_TOPOLOGY.md)
- **Agent Registry:** `pmoves/config/agent_registry.yaml` (not yet registered as agent)

## Open Items

- Live ToKenism/Flute smoke should confirm `tokenism.prosodic.bpm.v1` packets after W6-P2 publish path
- Verify Hardhat dependencies, local contract tests, and CI working directory
- Re-run temp-file and duplicate-layout audits before acting on stale counts
- Build chain settlement executor after Hardhat/deployment manifest coverage
- Keep zeta labeled heuristic until method design is reviewed
- Not registered as an agent in `agent_registry.yaml` — operates as library

<!-- GRAPHITI_MARK: CLAUDE-OPUS::TAC-TOPOLOGY-AUDIT::2026-02-20 -->
