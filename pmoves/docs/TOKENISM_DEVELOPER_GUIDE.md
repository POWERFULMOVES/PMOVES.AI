# ToKenism Developer Guide

**Layer:** L3 Applied
**Status:** Current with implementation caveats
**Last Updated:** 2026-05-22

> Developer reference for integrating ToKenism attribution into PMOVES.AI services. Covers all 8 TypeScript CHIT modules, the factory pattern, NATS publishing, and service integration patterns.

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Module Architecture](#module-architecture)
3. [Module Reference](#module-reference)
4. [Factory Pattern: createCHITSystem](#factory-pattern-createchitsystem)
5. [NATS Publishing](#nats-publishing)
6. [Service Integration Patterns](#service-integration-patterns)
7. [CGP Schema Versions](#cgp-schema-versions)
8. [Testing](#testing)
9. [Cross-References](#cross-references)

---

## Quick Start

```typescript
import { createCHITPublisher, createCHITSystem } from '@pmoves/chit';

// 1. Create system
const chit = createCHITSystem({
  dirichlet: { smoothingAlpha: 0.1, concentrationK: 1.0, decayHalfLife: 12 },
  hyperbolic: { curvature: -1, baseRadius: 0.3 },
  merkle: { strategy: 'per_week' },
  cgp: { namespace: 'pmoves.tokenism' },
  swarm: { optimizationTarget: 'gini_reduction' }
});

// 2. Record actions
const chitId = chit.attribution.recordAction(
  '0xMEMBER0...',
  'spending',
  50,
  12,
  'groceries'
);

// 3. Generate CGP
const cgp = chit.generator.generateWeeklyCGP(weekData, chit.attribution);

// 4. Publish to NATS
const publisher = createCHITPublisher(natsClient, { enabled: true });
const published = await publisher.publishWeeklyCGP(12, cgp, {
  gini: 0.42,
  poverty_rate: 0.15
});
```

`createCHITSystem()` returns the local math/attribution modules. NATS publishing is separate so services can inject their own connected client and choose best-effort or strict publishing behavior.

---

## Module Architecture

```
@pmoves/chit (index.ts)
├── DirichletWeights       (dirichlet-weights.ts)
├── HyperbolicEncoder      (hyperbolic-encoder.ts)
├── ShapeAttribution       (shape-attribution.ts)
├── CGPGenerator           (cgp-generator.ts)
├── SwarmAttribution       (swarm-attribution.ts)
├── ZetaInspiredFilter     (zeta-filter.ts)
└── CHITNATSPublisher      (chit-nats-publisher.ts)
```

**Location:** `PMOVES-ToKenism-Multi/integrations/contracts/chit/`

The CHIT package is Node-first TypeScript. Merkle hashing uses Node `crypto` for SHA-256 and `ethers` for keccak256, so browser/Deno use requires an explicit bundling or polyfill plan.

---

## Module Reference

### 1. DirichletWeights

**File:** `dirichlet-weights.ts`
**Purpose:** Transform raw contributions into normalized probability weights

```typescript
import { DirichletWeights } from '@pmoves/chit';

const dw = new DirichletWeights({
  smoothingAlpha: 0.1,      // Spikiness: 0.1 = spiky, 10 = uniform
  concentrationK: 1.0,      // Overall concentration
  decayHalfLife: 12          // Weeks before contribution halves
});

// Compute weights for a set of contributions
const weights = dw.computeWeights([
  { address: '0xABC', amount: 50, category: 'groceries' },
  { address: '0xDEF', amount: 5, category: 'groceries' },
  { address: '0xGHI', amount: 0, category: 'groceries' }
]);

// Result: ContributionWeight[]
// [
//   { address: '0xABC', weight: 0.91, rawContribution: 50, alphaComponent: 50.1 },
//   { address: '0xDEF', weight: 0.08, rawContribution: 5,  alphaComponent: 5.1 },
//   { address: '0xGHI', weight: 0.01, rawContribution: 0,  alphaComponent: 0.1 }
// ]
```

**Key Methods:**
- `computeWeights(contributions)`: Returns normalized weights
- `applyDecay(weights, weeksSinceActive)`: Apply temporal decay
- `getExpectedAttribution(category?)`: Get expected weights per category

### 2. HyperbolicEncoder

**File:** `hyperbolic-encoder.ts`
**Purpose:** Encode hierarchical data in Poincare disk space

```typescript
import { HyperbolicEncoder } from '@pmoves/chit';

const enc = new HyperbolicEncoder({
  curvature: -1,          // Fixed for Poincare disk
  baseRadius: 0.3,        // First-level node placement
  radiusGrowth: 1.3,      // Growth per hierarchy level
  angularSpread: Math.PI,
  maxRadius: 0.95
});

// Encode participants by activity level
const points = enc.encodeParticipants(participants);
// More active → closer to center, less active → outer edge

// Encode a hierarchy tree
const treePoints = enc.encodeHierarchy(rootNode, maxDepth=3);

// Compute hyperbolic distance
const dist = enc.hyperbolicDistance(pointA, pointB);

// Mobius addition (hyperbolic translation)
const translated = enc.mobiusAdd(pointA, pointB);
```

**Key Types:**
```typescript
interface PoincarePoint {
  x: number;        // [-1, 1]
  y: number;        // [-1, 1]
  radius: number;   // sqrt(x^2 + y^2), must be < 1.0
  theta: number;    // [0, 2*pi]
  id?: string;
  label?: string;
}
```

### 3. ShapeAttribution

**File:** `shape-attribution.ts`
**Purpose:** Immutable record of actions with Merkle proof generation

```typescript
import { ShapeAttribution } from '@pmoves/chit';

const attr = new ShapeAttribution({
  merkle: {
    strategy: 'per_week', // per_week | rolling | per_contract
    hashAlgorithm: 'sha256',
    signProofs: false
  }
});

// Record an action
const chitId = attr.recordAction(
  '0xMEMBER0...',
  'spending',
  50,
  12,
  'groceries'
);
// Returns: "chit-1a2b3c-0001"

// Get Merkle proof for verification
const record = attr.getRecord(chitId);
if (!record) throw new Error(`Missing attribution record: ${chitId}`);
const proof = record.proof;
// { merkleRoot, leafHash, path, pathIndices, signature? }

// Verify a proof
const valid = attr.verifyProof(proof.leafHash, proof);
// true

// Export as CGP
const cgp = attr.exportCGP(12);
```

**Action Types:**
- `token_received` — Token distribution
- `spending` — Economic transaction
- `group_contribution` — Group savings
- `staking` — Lock position
- `voting` — Governance participation
- `loyalty_earned` — Streak building
- `reward_claimed` — Pool distributions

**Merkle Tree Strategies:**

| Strategy | Scope | Use Case |
|----------|-------|----------|
| `per_week` | All actions in one week | Weekly accountability |
| `rolling` | All historical actions | Full audit trail |
| `per_contract` | By contract type | Contract-specific proofs |

### 4. CGPGenerator

**File:** `cgp-generator.ts`
**Purpose:** Generate valid CGP v1.0 documents from economic data

```typescript
import { CGPGenerator } from '@pmoves/chit';

const gen = new CGPGenerator({
  namespace: 'pmoves.tokenism',
  spec: 'chit.cgp.v1.0'
});

// Generate weekly CGP
const cgp = gen.generateWeeklyCGP(weekData, attribution);

// weekData shape:
// {
//   week: 12,
//   members: [...],
//   transactions: [...],
//   metrics: { gini, poverty_rate, total_wealth, ... }
// }
```

**Contract → Super-Node Mapping:**

| Contract | Super-Node ID | Label |
|----------|--------------|-------|
| GroToken | `grotoken-week-{N}` | GroToken Distribution |
| FoodUSD | `foodusd-week-{N}` | FoodUSD Transactions |
| GroupPurchase | `grouppurchase-week-{N}` | Group Purchases |
| GroVault | `grovault-week-{N}` | Staking Positions |
| CoopGovernor | `coopgovernor-week-{N}` | Governance Votes |
| RewardsPool | `rewardspool-week-{N}` | Reward Claims |
| LoyaltyPoints | `loyaltypoints-week-{N}` | Loyalty Events |

### 5. SwarmAttribution

**File:** `swarm-attribution.ts`
**Purpose:** Track optimization experiments and fitness across simulation runs

This module records generation metadata and bounded fitness scores. It does not perform mutation, crossover, selection, or particle updates. Real PSO/evolutionary operators belong to the PMOVES EvoSwarm/model-fitness workstream once runner topology and trusted identities are available.

```typescript
import { SwarmAttribution } from '@pmoves/chit';

const swarm = new SwarmAttribution({
  optimizationTarget: 'gini_reduction'
  // Options: gini_reduction | wealth_growth | participation |
  //          poverty_reduction | balanced | custom
});

// Evaluate fitness for a week
const fitness = swarm.calculateFitness(weekData);
// Returns: 0.0 to 1.0

// Create swarm meta for NATS
const meta = swarm.createSwarmMeta(weekData);

// Track populations
swarm.createPopulation('pop-42', 'weekly-gini-tracking');
swarm.recordGeneration('pop-42', 5, weekData);
```

**Fitness Targets:**

| Target | Scoring | Description |
|--------|---------|-------------|
| `gini_reduction` | `1 - max(0, (gini - 0.3) / 0.7)` | Minimize inequality |
| `wealth_growth` | `min(1, growth_rate / target)` | Maximize total wealth |
| `participation` | `participation_rate` | Maximize engagement |
| `poverty_reduction` | `1 - poverty_rate` | Minimize poverty |
| `balanced` | Equal weight of all above | Multi-objective |

### 6. ZetaInspiredFilter

**File:** `zeta-filter.ts`
**Purpose:** Apply a zeta-zero-weighted heuristic transform to CGP spectra

This is not a validated Riemann zeta spectral method. Treat it as an experimental weighting heuristic until a separate method-design review accepts the math.

```typescript
import { ZetaInspiredFilter } from '@pmoves/chit';

const zeta = new ZetaInspiredFilter({
  numZeros: 10,           // 1-20 zeros (default: 10)
  decayFactor: 0.9,       // Higher zeros decay (default: 0.9)
  normalizeOutput: true
});

// Filter a spectrum
const filtered = zeta.filterSpectrum([0.08, 0.11, 0.15, 0.22, 0.18, 0.12, 0.08, 0.06]);

// Get spectral analysis
const analysis = zeta.analyzeSpectrum(spectrum);
// { filtered, dominantIndex, concentration, entropy }

// Compute similarity between two spectra in zeta-weighted space
const similarity = zeta.spectralSimilarity(spectrumA, spectrumB);
```

**First 10 Riemann Zeta Zeros (gamma_k):**
```
14.1347, 21.0220, 25.0109, 30.4249, 32.9351,
37.5862, 40.9187, 43.3271, 48.0052, 49.7738
```

### 7. CHITNATSPublisher

**File:** `chit-nats-publisher.ts`
**Purpose:** Publish CHIT events to the NATS event fabric

```typescript
import { CHITNATSPublisher } from '@pmoves/chit';

const publisher = new CHITNATSPublisher(natsClient, {
  enabled: true,
  strictPublish: false
});

// Publish attribution record
const record = chit.attribution.getRecord(chitId);
if (!record) throw new Error(`Missing attribution record: ${chitId}`);
await publisher.publishAttributionRecorded(record);

// Publish weekly CGP
await publisher.publishWeeklyCGP(12, cgp, {
  gini: 0.42,
  poverty_rate: 0.15
});

// Publish swarm population update
await publisher.publishSwarmPopulation(meta, generation);

// Publish CGP ready for consumption
await publisher.publishCGPReady(cgp, { source: 'weekly-sim' });
```

Publisher methods return `true` on success and `false` on best-effort validation/connect failure. Set `strictPublish: true` when invalid payloads or disconnected clients should throw.

**Published Subjects:**

| Method | NATS Subject |
|--------|-------------|
| `publishAttributionRecorded` | `tokenism.attribution.recorded.v1` |
| `publishWeeklyCGP` | `tokenism.cgp.weekly.v1` |
| `publishSwarmPopulation` | `tokenism.swarm.population.v1` |
| `publishCGPReady` | `tokenism.cgp.ready.v1` |

---

## Factory Pattern: createCHITSystem

The recommended way to use the CHIT modules is through the factory:

```typescript
import { createCHITSystem } from '@pmoves/chit';

const chit = createCHITSystem({
  dirichlet: {
    smoothingAlpha: 0.1,
    concentrationK: 1.0,
    decayHalfLife: 12
  },
  hyperbolic: {
    curvature: -1,
    baseRadius: 0.3,
    radiusGrowth: 1.3,
    maxRadius: 0.95
  },
  merkle: {
    strategy: 'per_week'
  },
  cgp: {
    namespace: 'pmoves.tokenism',
    spec: 'chit.cgp.v1.0'
  },
  swarm: {
    optimizationTarget: 'gini_reduction'
  }
});

// Access subsystems
chit.dirichlet      // DirichletWeights instance
chit.encoder        // HyperbolicEncoder instance
chit.attribution    // ShapeAttribution instance
chit.generator      // CGPGenerator instance
chit.swarm          // SwarmAttribution instance
chit.zeta           // ZetaInspiredFilter instance
```

Create `CHITNATSPublisher` separately with the service-owned NATS client.

---

## NATS Publishing

### Subject Hierarchy

```
tokenism.
├── attribution.recorded.v1     # Per-action attribution
├── cgp.weekly.v1               # Weekly CGP summary
├── cgp.ready.v1                # CGP ready for consumption
├── swarm.population.v1         # Swarm fitness update
├── geometry.event.v1           # Voice synthesis events
└── credential.rotated.v1       # Credential rotation audit
```

### Consumer Patterns

**Hi-RAG v2** subscribes to:
- `tokenism.cgp.ready.v1` — indexes CGP for retrieval

**EvoSwarm** subscribes to:
- `tokenism.swarm.population.v1` — feeds fitness into parameter evolution

**Shape Store** subscribes to:
- `tokenism.cgp.ready.v1` — persists CGP to database

**Analytics** subscribes to:
- `tokenism.cgp.weekly.v1` — generates dashboards
- `tokenism.attribution.recorded.v1` — real-time attribution tracking

---

## Service Integration Patterns

### Pattern 1: Attribution-Only Service

For services that only record contributions without generating CGPs:

```typescript
import { ShapeAttribution, CHITNATSPublisher } from '@pmoves/chit';

const attribution = new ShapeAttribution({
  merkle: {
    strategy: 'rolling',
    hashAlgorithm: 'sha256',
    signProofs: false
  }
});
const publisher = new CHITNATSPublisher(natsClient);

// On each economic event:
app.post('/transaction', async (req) => {
  const week = getCurrentWeek();
  const chitId = attribution.recordAction(
    req.body.address,
    'spending',
    req.body.amount,
    week,
    req.body.category
  );
  const record = attribution.getRecord(chitId);
  if (!record) throw new Error(`Missing attribution record: ${chitId}`);

  await publisher.publishAttributionRecorded(record);

  return { chit_id: chitId };
});
```

### Pattern 2: Full CGP Generation Service

For services that produce complete CGPs:

```typescript
import { CHITNATSPublisher, createCHITSystem } from '@pmoves/chit';

const chit = createCHITSystem({ /* config */ });
const publisher = new CHITNATSPublisher(natsClient, { strictPublish: true });

// Weekly cron job:
cron.schedule('0 0 * * 0', async () => {
  const weekData = await fetchWeekData(getCurrentWeek());
  const cgp = chit.generator.generateWeeklyCGP(weekData, chit.attribution);
  const metrics = chit.swarm.createSwarmMeta(weekData);

  await publisher.publishWeeklyCGP(getCurrentWeek(), cgp, weekData.metrics);
  await publisher.publishSwarmPopulation(metrics, 0);
  await publisher.publishCGPReady(cgp, { source: 'weekly-cron' });
});
```

### Pattern 3: CGP Consumer Service

For services that consume CGPs but don't produce them:

```typescript
import { connect, StringCodec } from 'nats';

const nc = await connect({ servers: 'nats://nats:pmoves@nats:4222' });
const sc = StringCodec();

const sub = nc.subscribe('tokenism.cgp.ready.v1');
for await (const msg of sub) {
  const cgp = JSON.parse(sc.decode(msg.data));

  // Validate CGP
  if (cgp.spec !== 'chit.cgp.v1.0') continue;

  // Process constellations
  for (const superNode of cgp.super_nodes) {
    for (const constellation of superNode.constellations) {
      await indexConstellation(constellation);
    }
  }
}
```

---

## CGP Schema Versions

| Version | Status | Features |
|---------|--------|----------|
| `chit.cgp.v1.0` | **Current** | Current schema with attribution, Merkle proofs, and optional geometry metadata |
| `chit.cgp.v0.2` | Stable compatibility | Attribution + Merkle proofs |
| `chit.cgp.v0.1` | Legacy | Basic super_nodes only |

### Version Detection

```typescript
function getCGPVersion(cgp: any): string {
  const spec = cgp.spec || cgp.version;
  const aliases: Record<string, string> = {
    'cgp.v1': 'chit.cgp.v1.0',
    'geometry.cgp.v1': 'chit.cgp.v1.0'
  };
  return aliases[spec] || spec;
}
```

---

## Testing

### Unit Tests

```typescript
import { createCHITSystem } from '@pmoves/chit';
import { describe, it, expect } from 'vitest';

describe('CHIT System', () => {
  it('records attribution and generates CGP', () => {
    const chit = createCHITSystem({ /* defaults */ });

    const chitId = chit.attribution.recordAction(
      '0xTEST',
      'spending',
      100,
      1,
      'groceries'
    );

    expect(chitId).toMatch(/^chit-/);

    const record = chit.attribution.getRecord(chitId);
    expect(record).toBeDefined();
    const proof = record!.proof;
    expect(chit.attribution.verifyProof(proof.leafHash, proof)).toBe(true);
  });

  it('computes fair Dirichlet weights', () => {
    const chit = createCHITSystem({ /* defaults */ });

    const weights = chit.dirichlet.computeWeights([
      { address: 'A', amount: 100, category: 'test' },
      { address: 'B', amount: 0, category: 'test' }
    ]);

    // Both must be > 0 when both participants are represented in the input set.
    expect(weights[0].weight).toBeGreaterThan(0);
    expect(weights[1].weight).toBeGreaterThan(0);

    // Sum to 1
    const sum = weights.reduce((s, w) => s + w.weight, 0);
    expect(Math.abs(sum - 1.0)).toBeLessThan(1e-6);
  });
});
```

### Integration Tests

```typescript
describe('NATS Integration', () => {
  it('publishes attribution event', async () => {
    const attribution = new ShapeAttribution();
    const chitId = attribution.recordAction('0xTEST', 'spending', 50, 1, 'test');
    const record = attribution.getRecord(chitId);
    expect(record).toBeDefined();

    const publisher = new CHITNATSPublisher(natsClient, { strictPublish: true });

    const ok = await publisher.publishAttributionRecorded(record!);

    expect(ok).toBe(true);
  });
});
```

---

## Cross-References

- [TOKENISM_ECONOMIC_MODEL.md](TOKENISM_ECONOMIC_MODEL.md) — Economic model and token lifecycle
- [CATACLYSM_CROSSLINKS.md](CATACLYSM_CROSSLINKS.md) — Business vision bridge
- [CHIT_INTEGRATION_STATUS.md](audit/CHIT_INTEGRATION_STATUS.md) — Per-service integration status
- [MATH_PIPELINE_WALKTHROUGH.md](PMOVESCHIT/MATH_PIPELINE_WALKTHROUGH.md) — Complete encoding pipeline
- [geometry-nats-subjects.md](../.claude/context/geometry-nats-subjects.md) — NATS subject catalog
- [TypeScript modules source](../../PMOVES-ToKenism-Multi/integrations/contracts/chit/) — Implementation

---

*This document is a living artifact tracked by [CHIT_CHANGE_TRACKER.md](CHIT_CHANGE_TRACKER.md).*
