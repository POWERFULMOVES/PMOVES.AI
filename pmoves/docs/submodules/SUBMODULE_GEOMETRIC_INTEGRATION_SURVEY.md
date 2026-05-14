# PMOVES.AI Submodule Geometric Intelligence Integration Survey

**Date:** 2026-02-08
**Scope:** 27+ PMOVES.AI submodules
**Focus:** CHIT/GEOMETRY BUS integration patterns

---

## Executive Summary

This survey documents CHIT (Cymatic-Holographic Information Transfer) and GEOMETRY BUS integration across all PMOVES.AI submodules. The geometric intelligence layer enables hyperbolic encoding, CGP (CHIT Geometry Packet) publishing, and NATS-based event coordination.

### Key Findings

- **24 submodules** have CHIT integration (`PMOVES.AI_INTEGRATION.md`, `secrets_manifest_v2.yaml`)
- **3 services** actively publish to `tokenism.cgp.*` NATS subjects
- **5 services** publish to `geometry.*` NATS subjects
- **1 primary CGP generator**: PMOVES-ToKenism-Multi with full CHIT TypeScript contracts
- **1 geometric encoder**: PMOVES-DoX with hyperbolic/Poincaré analysis
- **Tier-based credential loading** across 10+ submodules

---

## Integration Matrix

### Submodule × Integration Feature Table

| Submodule | CHIT Integration | Secrets Manifest | Bootstrap Script | Tier Files | CGP Publisher | Geometry Publisher | Branch |
|-----------|------------------|------------------|------------------|------------|--------------|-------------------|--------|
| PMOVES-Agent-Zero | ✅ | ✅ | ✅ | ✅ | ✅ (via MCP) | ✅ (geometry.*) | PMOVES.AI-Edition-Hardened |
| PMOVES-Archon | ✅ | ✅ | ❌ | ✅ (agent) | ❌ | ❌ | PMOVES.AI-Edition-Hardened |
| PMOVES-BoTZ | ✅ | ✅ | ❌ | ✅ (agent) | ❌ | ❌ | main |
| PMOVES-DoX | ✅ | ✅ | ❌ | ✅ (agent) | ✅ (tokenism.cgp.*) | ✅ (geometry.*) | PMOVES.AI-Edition-Hardened-DoX |
| PMOVES-ToKenism-Multi | ✅ | ✅ | ❌ | ✅ (agent/api/data/llm/media/worker) | ✅ (tokenism.cgp.*) | ✅ (geometry.*) | PMOVES.AI-Edition-Hardened |
| PMOVES-Pipecat | ✅ | ✅ | ❌ | ✅ (media) | ❌ | ❌ | PMOVES.AI-Edition-Hardened |
| PMOVES-Jellyfin | ✅ | ✅ | ❌ | ✅ (media) | ❌ | ❌ | PMOVES.AI-Edition-Hardened |
| PMOVES-Deep-Serch | ✅ | ✅ | ❌ | ✅ (api) | ❌ | ❌ | main |
| PMOVES-Open-Notebook | ✅ | ✅ | ❌ | ✅ (worker) | ❌ | ❌ | main |
| PMOVES-n8n | ✅ | ✅ | ❌ | ✅ (worker) | ❌ | ❌ | PMOVES.AI-Edition-Hardened |
| PMOVES-HiRAG | ✅ | ✅ | ❌ | ✅ (api) | ❌ | ❌ | PMOVES.AI-Edition-Hardened |
| PMOVES-tensorzero | ✅ | ✅ | ❌ | ✅ (llm) | ❌ | ❌ | PMOVES.AI-Edition-Hardened |
| PMOVES-Creator | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | main |
| PMOVES-A2UI | ✅ | ✅ | ❌ | ✅ (ui) | ❌ | ❌ | main |
| PMOVES-Tailscale | ✅ | ✅ | ❌ | ✅ (data) | ❌ | ❌ | main |
| PMOVES-E2b-Spells | ✅ | ✅ | ❌ | ✅ (worker) | ❌ | ❌ | main |
| PMOVES-Pinokio-Ultimate-TTS-Studio | ✅ | ✅ | ❌ | ✅ (media) | ❌ | ❌ | main |
| PMOVES-Wealth | ✅ | ✅ | ❌ | ✅ (agent) | ❌ | ❌ | main |
| PMOVES-crush | ✅ | ✅ | ❌ | ✅ (api/data) | ❌ | ❌ | main |
| PMOVES-Danger-infra | ✅ | ✅ | ❌ | ✅ (api) | ❌ | ❌ | main |
| PMOVES-supabase | N/A | ❌ | ❌ | ❌ | ❌ | ❌ | main |
| PMOVES-transcribe-and-fetch | ❌ | ❌ | ❌ | ✅ (api/llm/media/worker) | ❌ | ❌ | main |
| PMOVES-llama-throughput-lab | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | main |
| PMOVES-Headscale | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | main |
| PMOVES-Remote-View | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | main |
| PMOVES-surf | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | main |
| PMOVES-MAI-UI | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | main |

### Legend

- **CHIT Integration**: Has `PMOVES.AI_INTEGRATION.md` documenting geometric patterns
- **Secrets Manifest**: Has `chit/secrets_manifest_v2.yaml` for CHIT credentials
- **Bootstrap Script**: Has `scripts/bootstrap_credentials.sh` for credential loading
- **Tier Files**: Has `env.tier-*` files for tier-based credential loading
- **CGP Publisher**: Publishes to `tokenism.cgp.*` NATS subjects
- **Geometry Publisher**: Publishes to `geometry.*` NATS subjects

---

## CGP Producers (Services Publishing Geometric Data)

### Primary CGP Publishers

| Service | Location | NATS Subjects | Description |
|---------|----------|---------------|-------------|
| **PMOVES-DoX** | `/PMOVES-DoX/backend/app/services/chit_service.py` | `tokenism.cgp.ready.v1`, `geometry.*` | Document intelligence with hyperbolic encoding |
| **PMOVES-ToKenism-Multi** | `/PMOVES-ToKenism-Multi/integrations/contracts/chit/` | `tokenism.cgp.ready.v1`, `tokenism.cgp.weekly.v1` | Economic simulation with Dirichlet attribution |
| **Agent Zero** | `/pmoves/services/agent-zero/mcp_server.py` | `geometry.*`, `tokenism.*` | MCP bridge for CGP commands |
| **Evo-Controller** | `/pmoves/services/evo-controller/app.py` | `geometry.swarm.meta.v1` | Swarm optimization metadata |
| **Flute-Gateway** | `/pmoves/services/flute-gateway/main.py` | `tokenism.geometry.event.v1` | Voice prosody geometry events |
| **Tokenism-Simulator** | `/pmoves/services/tokenism-simulator/` | `tokenism.cgp.ready.v1` | Simulation CGP generation |

### CGP Publishing Code Examples

**PMOVES-ToKenism-Multi (TypeScript)**:
```typescript
// Publishes to tokenism.cgp.ready.v1
async publishCGPReady(
  cgp: CGPDocument,
  metadata?: { week?: number; source?: string }
): Promise<void> {
  await this.client.publish(
    CHIT_NATS_SUBJECTS.cgpReady,  // "tokenism.cgp.ready.v1"
    payload
  );
}
```

**PMOVES-DoX (Python)**:
```python
# Publishes to tokenism.cgp.ready.v1
async def publish_cgp(self, cgp: Dict[str, Any],
                     subject: str = "tokenism.cgp.ready.v1") -> bool:
    await self.js.publish(subject, json.dumps(cgp).encode())
```

---

## CGP Consumers (Services Consuming Geometric Data)

| Service | Location | NATS Subjects | Usage |
|---------|----------|---------------|-------|
| **PMOVES-DoX** | `/PMOVES-DoX/backend/app/services/chit_service.py` | `tokenism.cgp.ready.v1` | Subscribes via JetStream durable consumer |
| **Publisher-Discord** | `/pmoves/services/publisher-discord/main.py` | `tokenism.cgp.weekly.v1`, `tokenism.cgp.ready.v1` | Discord notifications for CGP events |
| **DeepResearch** | `/pmoves/services/deepresearch/worker.py` | `tokenism.cgp.ready.v1` | CGP subject configuration for research |

### Consumer Code Examples

**PMOVES-DoX (Python)**:
```python
await self.js.subscribe("tokenism.cgp.ready.v1", cb=cb,
                       durable="dox-geometry-consumer")
```

**Publisher-Discord (Python)**:
```python
# Listens for CGP events
SUBJECTS = "tokenism.attribution.recorded.v1,tokenism.cgp.weekly.v1,tokenism.cgp.ready.v1"
COLORS = {
    "tokenism.cgp.weekly.v1": 0x06b6d4,
    "tokenism.cgp.ready.v1": 0x0891b2,
}
```

---

## Tier Distribution (env.tier-* Architecture)

### Tier Categories

| Tier | Description | Submodules |
|------|-------------|------------|
| **agent** | Agent/orchestrator services | Agent-Zero, Archon, BoTZ, DoX, ToKenism-Multi, Wealth |
| **api** | API gateway services | Deep-Serch, Danger-infra, crush, HiRAG, transcribe-and-fetch |
| **data** | Data storage services | Tailscale, ToKenism-Multi, crush |
| **llm** | LLM/gateway services | tensorzero, transcribe-and-fetch, ToKenism-Multi |
| **media** | Media processing services | Pipecat, Jellyfin, Pinokio-Ultimate-TTS-Studio |
| **worker** | Background workers | Creator, E2b-Spells, n8n, Open-Notebook, transcribe-and-fetch |
| **ui** | Frontend services | A2UI |
| **supabase** | Database services | pmoves (root) |
| **vpn** | VPN services | pmoves (root, example only) |

### Tier File Examples

**Agent Tier** (`PMOVES-Agent-Zero/env.tier-agent.sh`):
```bash
# Loads AGENT tier credentials from CHIT vault
# Precedence: Docker secrets > GH actions > CHIT vault > env vars > parent repo
```

**Data Tier** (`PMOVES-ToKenism-Multi/env.tier-data`):
```bash
# Loads DATA tier credentials for geometric data stores
```

**Multi-Tier** (`PMOVES-ToKenism-Multi/`):
```
env.tier-agent      # Agent orchestrator
env.tier-api        # API gateway
env.tier-data       # Geometric data stores
env.tier-llm        # LLM providers
env.tier-media      # Media processing
env.tier-worker     # Background workers
```

---

## Geometric Encoding Implementations

### 1. Hyperbolic Encoder (Poincaré Disk)

**Location:** `/PMOVES-ToKenism-Multi/integrations/contracts/chit/hyperbolic-encoder.ts`

**Capabilities:**
- Poincaré disk coordinate system (x, y in [-1, 1])
- Hierarchical encoding (center = aggregate, outer = specific)
- Möbius transformations for nesting
- Hyperbolic distance calculation
- CGP super node generation

**Key Functions:**
```typescript
class HyperbolicEncoder {
  // Convert Cartesian to polar
  toPolar(x: number, y: number): { radius: number; theta: number }

  // Calculate hyperbolic distance
  hyperbolicDistance(a: PoincarePoint, b: PoincarePoint): number

  // Encode hierarchy to Poincaré disk
  encodeHierarchy(root: HierarchyNode): CGPSuperNode[]
}
```

### 2. Geometry Engine (Curvature Analysis)

**Location:** `/PMOVES-DoX/backend/app/services/geometry_engine.py`

**Capabilities:**
- Delta-hyperbolicity computation (4-point Gromov product)
- Curvature detection (hyperbolic/spherical/euclidean)
- Riemann Zeta spectral analysis
- CHIT manifold config generation
- Semantic clustering with manifold detection
- Geodesic distance computation
- Knowledge gap detection

**Key Functions:**
```python
class GeometryEngine:
  def analyze_curvature(self, embeddings: List[List[float]]) -> Dict[str, float]
  def compute_exact_delta(self, embeddings: List[List[float]]) -> float
  def compute_zeta_spectrum(self, embeddings: List[List[float]]) -> Tuple[List, List]
  def generate_chit_config(self, analysis: Dict[str, float]) -> Dict[str, Any]
  def analyze_semantic_clusters(self, embeddings, labels) -> Dict[str, Any]
  def detect_knowledge_gaps(self, embeddings, threshold) -> List[Dict]
```

### 3. CHIT NATS Publisher

**Location:** `/PMOVES-ToKenism-Multi/integrations/contracts/chit/chit-nats-publisher.ts`

**Capabilities:**
- Publish CGP to `tokenism.cgp.ready.v1`
- Publish weekly CGP to `tokenism.cgp.weekly.v1`
- Publish swarm population to `tokenism.swarm.population.v1`
- Publish attribution records to `tokenism.attribution.recorded.v1`

**Key Functions:**
```typescript
class CHITNATSPublisher {
  async publishCGPReady(cgp: CGPDocument, metadata?): Promise<void>
  async publishWeeklyCGP(week: number, cgp: CGPDocument, metrics?): Promise<void>
  async publishSwarmPopulation(meta: SwarmMeta, generation?): Promise<void>
  async publishAttributionRecorded(record: AttributionRecord): Promise<void>
}
```

---

## CHIT Integration Pattern

### Standard CHIT Integration Files

| File | Purpose | Location |
|------|---------|----------|
| `PMOVES.AI_INTEGRATION.md` | Integration documentation | Submodule root |
| `chit/secrets_manifest_v2.yaml` | CHIT credentials manifest | Submodule root |
| `scripts/bootstrap_credentials.sh` | Credential bootstrap script | Submodule root |
| `env.tier-*` | Tier-based environment loading | Submodule root |

### Secrets Manifest Structure

**Example:** `PMOVES-ToKenism-Multi/chit/secrets_manifest_v2.yaml`
```yaml
# CHIT Geometry Secrets Manifest v2
# Defines credentials for geometric intelligence operations

geometric:
  enabled: true
  cgp_namespace: "pmoves.tokenism"

nats:
  url: "nats://nats:pmoves@nats:4222"
  jetstream: true
  subjects:
    cgp_ready: "tokenism.cgp.ready.v1"
    cgp_weekly: "tokenism.cgp.weekly.v1"
    geometry: "geometry.*"

hyperbolic:
  curvature: -1
  max_radius: 0.95
```

### Integration Documentation Pattern

**Example:** `PMOVES-DoX/PMOVES.AI_INTEGRATION.md`
```markdown
# PMOVES.AI Integration

## CHIT Protocol

### Geometric Intelligence
- Curvature detection via `GeometryEngine`
- CHIT service publishes to `tokenism.cgp.ready.v1`
- Subscribes to `geometry.*` for real-time updates

### NATS Configuration
- Standalone: `ws://localhost:9223`
- Docked: `ws://localhost:9222` (parent PMOVES.AI)
```

---

## Integration Gaps (Submodules Missing Integration)

### No CHIT Integration

| Submodule | Type | Recommendation |
|-----------|------|----------------|
| PMOVES-supabase | Infrastructure | Add CHIT for database geometry monitoring |
| PMOVES-transcribe-and-fetch | Worker | Add CGP for transcription geometry |
| PMOVES-llama-throughput-lab | Testing | Add hyperbolic encoding for latency metrics |
| PMOVES-Headscale | VPN | Add geometry for network topology |
| PMOVES-Remote-View | UI | Add hyperbolic navigation |
| PMOVES-surf | Utility | Consider CHIT for surf patterns |
| PMOVES-MAI-UI | UI | Add geometric visualization |

### Missing Tier Files

| Submodule | Current State | Action Needed |
|-----------|--------------|---------------|
| PMOVES-Creator | No tier files | Add `env.tier-worker.sh` |
| PMOVES-transcribe-and-fetch | Has tier files | Add CHIT integration |
| PMOVES-llama-throughput-lab | No tier files | Add `env.tier-llm.sh` |

---

## NATS Subject Catalog (Geometric Intelligence)

### tokenism.* Subjects

| Subject | Publisher | Consumer | Purpose |
|---------|-----------|----------|---------|
| `tokenism.cgp.ready.v1` | DoX, ToKenism, Tokenism-Simulator | DoX, Publisher-Discord, DeepResearch | Immediate CGP consumption |
| `tokenism.cgp.weekly.v1` | ToKenism | Publisher-Discord | Weekly CGP summary |
| `tokenism.attribution.recorded.v1` | ToKenism | Publisher-Discord | Attribution events |
| `tokenism.swarm.population.v1` | Evo-Controller | Publisher-Discord | Swarm metadata |
| `tokenism.geometry.event.v1` | Flute-Gateway | Various | Voice prosody geometry |

### geometry.* Subjects

| Subject | Publisher | Consumer | Purpose |
|---------|-----------|----------|---------|
| `geometry.swarm.meta.v1` | Evo-Controller, Agent Zero | Various | Swarm optimization metadata |
| `geometry.event.manifold` | DoX (simulate) | DoX | Manifold updates |
| `geometry.event.manifold_update` | DoX | DoX | Manifold change events |
| `geometry.event.constellation` | DoX (simulate) | DoX | Constellation geometry |
| `geometry.event.test` | DoX (verify) | DoX | Testing |

---

## Synchronization Status (Branch Alignment)

### PMOVES.AI-Edition-Hardened Branch

The following submodules are aligned on `PMOVES.AI-Edition-Hardened`:
- PMOVES-Agent-Zero ✅
- PMOVES-Archon ✅
- PMOVES-BoTZ (main, PRs pending)
- PMOVES-DoX (PMOVES.AI-Edition-Hardened-DoX)
- PMOVES-ToKenism-Multi ✅
- PMOVES-Pipecat ✅
- PMOVES-Jellyfin ✅
- PMOVES-n8n ✅
- PMOVES-HiRAG ✅
- PMOVES-tensorzero ✅

### Branch Summary

| Branch | Count | Submodules |
|--------|-------|------------|
| `PMOVES.AI-Edition-Hardened` | 10 | Primary production submodules |
| `main` | 15 | Development/testing submodules |
| `PMOVES.AI-Edition-Hardened-DoX` | 1 | PMOVES-DoX specific branch |

---

## Bootstrap Implementation

### Bootstrap Script Locations

| Script | Location | Usage |
|--------|----------|-------|
| Main bootstrap | `/scripts/bootstrap_credentials.sh` | Parent repo credential loader |
| Agent-Zero bootstrap | `/PMOVES-Agent-Zero/scripts/bootstrap_credentials.sh` | Agent-specific bootstrap |
| DoX external | `/PMOVES-DoX/external/PMOVES-Agent-Zero/scripts/bootstrap_credentials.sh` | Embedded Agent Zero |

### Bootstrap Precedence Chain

1. Docker secrets (`/run/secrets/`)
2. GitHub Actions secrets
3. CHIT Vault (HTTP API)
4. Environment variables
5. Parent PMOVES.AI repo files

---

## Recommendations

### For Geometric Intelligence Adoption

1. **Add CHIT to all tier-based services**: Create `chit/secrets_manifest_v2.yaml` for credential management
2. **Extend CGP publishing**: Media services (Pipecat, Jellyfin) should publish geometry events
3. **Unify tier architecture**: Standardize `env.tier-*` across all submodules
4. **Document geometric patterns**: Add `PMOVES.AI_INTEGRATION.md` to all submodules
5. **Create geometric tests**: Add geometric data validation to CI

### For Synchronization

1. **Align branches**: Move remaining `main` branch submodules to `PMOVES.AI-Edition-Hardened`
2. **PR workflow**: Create geometric feature PRs against hardened branch
3. **Submodule testing**: Add geometric integration tests to CI pipeline

---

## Appendix: File Locations Reference

### CHIT Contracts

```
/PMOVES-ToKenism-Multi/integrations/contracts/chit/
├── index.ts                    # CHIT system exports
├── chit-nats-publisher.ts      # NATS publisher
├── hyperbolic-encoder.ts       # Poincaré encoding
├── cgp-generator.ts            # CGP document generation
├── dirichlet-weights.ts        # Probabilistic attribution
├── shape-attribution.ts        # Merkle proofs
├── swarm-attribution.ts        # Swarm optimization
└── zeta-filter.ts              # Riemann zeta spectral
```

### Geometry Engine

```
/PMOVES-DoX/backend/app/services/
├── geometry_engine.py          # Curvature analysis
└── chit_service.py             # NATS geometry bus
```

### NATS Geometry Services

```
/pmoves/services/
├── agent-zero/mcp_server.py    # MCP bridge
├── evo-controller/app.py        # Swarm optimization
├── tokenism-simulator/          # Economic simulation
└── publisher-discord/main.py    # Discord notifications
```

---

**Generated:** 2026-02-08
**Survey Tool:** Claude Code CLI
**Repository:** PMOVES.AI
