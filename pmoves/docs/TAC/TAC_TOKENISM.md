# TAC Tree: ToKenism-Multi

> Technology-Architecture-Context tree for the ToKenism economic simulation and CHIT attribution engine.

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

1. **9 CHIT TypeScript modules** (`integrations/contracts/chit/`)
   - `chitEncoder.ts` — CGP packet encoding
   - `chitDecoder.ts` — CGP packet decoding
   - `dirichletAttribution.ts` — Dirichlet-weighted contribution scoring
   - `merkleAttribution.ts` — Merkle tree verification
   - `chitTypes.ts` — Type definitions for CGP v0.1/v0.2
   - `musicMapping.ts` — BPM/frequency/note conversion utilities
   - `poincareDisk.ts` — Hyperbolic geometry embeddings
   - `zetaSpectrum.ts` — Zeta-inspired spectral filtering
   - `chitValidator.ts` — CGP packet validation

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
| `tokenism.swarm.population.v1` | Publishes | Swarm optimization population update |
| `tokenism.geometry.event.v1` | (consumed from Flute) | Voice synthesis attribution events |
| `tokenism.prosodic.bpm.v1` | (consumed from Flute) | BPM-encoded prosodic timeline events |

## CHIT Integration Status

ToKenism **is** the CHIT engine — all CHIT integration radiates from here.

| Capability | Status | Notes |
|------------|--------|-------|
| CGP v0.1 encoding | Active | Via `chitEncoder.ts` |
| CGP v0.2 attribution | Active | Dirichlet + Merkle extensions |
| Dirichlet weighting | Active | `dirichletAttribution.ts` |
| Merkle verification | Active | `merkleAttribution.ts` |
| Hyperbolic embedding | Active | `poincareDisk.ts` |
| Zeta spectral filtering | Active | `zetaSpectrum.ts` |
| BPM/music mapping | Active | `musicMapping.ts` |
| Smart contract attribution | Active | On-chain verification |

## Production Audit Checklist

| Requirement | Status | Notes |
|-------------|--------|-------|
| `/healthz` endpoint | N/A | Library, not service |
| `/metrics` (Prometheus) | None | No metrics endpoint |
| Auth (JWT/Bearer) | Partial | Smart contract auth only |
| Docker hardening | Yes | Standard patterns applied |
| NATS auth | Yes | Uses authenticated NATS |
| `env.shared` format | **P1** | Uses `export` syntax (Docker-incompatible) |
| Hardhat CI | **Issue** | Wrong `working-directory` in GitHub Actions |
| Temp files | **Issue** | 4 `.new` temp files need cleanup |
| Duplicate layout | **Issue** | Duplicate `layout.tsx` found |

## Security Stance

| Finding | Severity | Status |
|---------|----------|--------|
| `export` syntax in `env.shared` | P1 | **Open** |
| NATS_URL missing credentials | P1 | **Open** — defaults to `nats://nats:4222` |
| Hardhat CI wrong `working-directory` | P2 | **Open** |
| 4 `.new` temp files | P3 | Cleanup needed |

## musicMapping.ts ↔ Prosodic Integration

The `musicMapping.ts` module provides the mathematical foundation for BPM-prosodic encoding:

| Function | Prosodic Use | Description |
|----------|-------------|-------------|
| `midiToFreq()` | Voice pitch | Convert MIDI note to Hz for TTS pitch |
| `freqToY()` | Pitch contour visualization | Map Hz to visual Y coordinate |
| `buildTimeline()` | BPM timeline from chunks | Convert ProsodicChunk[] to TimelinePoint[] |
| Scale definitions | Emotional coloring | Major=happy, Minor=sad, Pentatonic=neutral |

**Scale → Prosodic Boundary Mapping:**

| Scale | Boundary Context | Musical Feel |
|-------|-----------------|-------------|
| `pentatonicMajor` | Default speech | Neutral, pleasant |
| `major` | Excited/positive content | Bright, uplifting |
| `minor` | Serious/sad content | Somber, reflective |
| `chromatic` | Technical/rapid content | Dense, information-rich |

## Cross-Links

- **Submodule:** `PMOVES-ToKenism-Multi/`
- **CHIT Modules:** `PMOVES-ToKenism-Multi/integrations/contracts/chit/`
- **GEOMETRY BUS:** `.claude/context/geometry-nats-subjects.md`
- **BPM Math:** `pmoves/docs/AGENTS/AGNOTE4482.BEATS.md`
- **Flute Prosodics:** [`pmoves/docs/FLUTE_PROSODIC_ARCHITECTURE.md`](../FLUTE_PROSODIC_ARCHITECTURE.md)
- **Integration Topology:** [`TAC_INTEGRATION_TOPOLOGY.md`](./TAC_INTEGRATION_TOPOLOGY.md)
- **Agent Registry:** `pmoves/config/agent_registry.yaml` (not yet registered as agent)

## Open Items

- `env.shared` uses `export` syntax incompatible with Docker `env_file`
- NATS_URL missing credentials in defaults
- Hardhat CI wrong `working-directory`
- 4 `.new` temp files need cleanup
- Duplicate `layout.tsx` found — needs deduplication
- Not registered as an agent in `agent_registry.yaml` — operates as library

<!-- GRAPHITI_MARK: CLAUDE-OPUS::TAC-TOPOLOGY-AUDIT::2026-02-20 -->
