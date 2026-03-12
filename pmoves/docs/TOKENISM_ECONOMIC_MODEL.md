# ToKenism Economic Model

**Layer:** L2 Conceptual / L4 Vision
**Status:** Current
**Last Updated:** 2026-03-11

> How CGP shape attribution maps to economic tokens in the PMOVES.AI cooperative economy. Covers the token lifecycle, simulation mechanics, fairness metrics, and the bridge between CHIT geometry and real-world economic impact.

---

## Table of Contents

1. [Overview](#overview)
2. [Economic Architecture](#economic-architecture)
3. [Token Lifecycle](#token-lifecycle)
4. [Contract Types](#contract-types)
5. [CGP Shape Attribution Flow](#cgp-shape-attribution-flow)
6. [Simulation Mechanics](#simulation-mechanics)
7. [Fairness Metrics](#fairness-metrics)
8. [NATS Event Integration](#nats-event-integration)
9. [Cooperative vs Traditional Model](#cooperative-vs-traditional-model)
10. [Cross-References](#cross-references)

---

## Overview

ToKenism bridges CHIT's mathematical geometry with real-world cooperative economics. The core premise:

> **Every economic action is a geometric event.** Spending, saving, staking, voting — each action creates a point in constellation space. The shape of these constellations determines fair attribution and wealth distribution.

### The Bridge: Geometry → Economics

```
Content/Action → Embedding → Constellation → CGP Packet → Attribution → Token
     |               |            |              |             |            |
  "Buy food"    384-dim vec   FoodUSD      spectrum+anchor  Dirichlet    GroToken
   $50 spend     normalized   cluster      energy dist.     weight=0.32   award
```

### Key Principles

1. **Geometric fairness**: Dirichlet distributions guarantee non-zero attribution for all participants
2. **Cryptographic accountability**: Merkle proofs make every attribution tamper-evident
3. **Evolutionary optimization**: EvoSwarm continuously improves attribution parameters
4. **Holographic transparency**: CGP spectra are publicly auditable without revealing raw data

---

## Economic Architecture

### Participants

| Role | Description | Actions |
|------|-------------|---------|
| **Members** | Cooperative participants | Spend, save, vote, stake |
| **Validators** | Trust anchors | Verify Merkle proofs, audit CGPs |
| **Operators** | Platform administrators | Configure parameters, manage contracts |
| **Agents** | AI services | Process transactions, generate CGPs |

### Token Types

| Token | Symbol | Purpose | Backing |
|-------|--------|---------|---------|
| **GroToken** | GRO | Community currency | Cooperative value creation |
| **FoodUSD** | FUSD | Food economy | Food purchasing power |

### Value Flow

```
Member Contribution → GroToken Award → Economic Activity → Attribution
        ↑                                                       │
        └───────── Reward Pool Distribution ←──────────────────┘
```

---

## Token Lifecycle

### Phase 1: Contribution Recording

When a member performs an economic action:

```typescript
const chitId = chit.attribution.recordAction({
  address: '0xMEMBER0...',
  action: 'spending',
  amount: 50.0,
  week: 12,
  category: 'groceries'
});
// Returns: chit-1a2b3c-0001
```

Each action gets a unique CHIT ID (format: `chit-{timestamp-base36}-{counter-base36}`).

### Phase 2: Dirichlet Weighting

Contributions are weighted using Dirichlet distributions:

```
alpha_i = smoothingAlpha + (amount * concentrationK)
weight_i = alpha_i / sum(all_alpha)
```

With smoothingAlpha = 0.1 and concentrationK = 1.0:
- $50 spending → alpha = 50.1 → proportional weight
- $5 spending → alpha = 5.1 → smaller but non-zero weight
- No activity → alpha = 0.1 → minimal but non-zero weight (fairness guarantee)

### Phase 3: Temporal Decay

Contributions decay over time to incentivize ongoing participation:

```
alpha_decayed = alpha * exp(-ln(2) / halfLife * weeks_since_last)
```

With halfLife = 12 weeks:
- Week 0: alpha retains 100%
- Week 12: alpha retains 50%
- Week 24: alpha retains 25%

### Phase 4: CGP Construction

Weekly CGPs capture the economic state as geometry:

```json
{
  "spec": "chit.cgp.v1.0",
  "meta": {
    "namespace": "pmoves.tokenism",
    "simulation_week": 12,
    "metrics": {
      "gini": 0.42,
      "poverty_rate": 0.15,
      "total_wealth": 125000
    }
  },
  "super_nodes": [
    {
      "id": "grotoken-week-12",
      "label": "GroToken Distribution",
      "constellations": [{ "anchor": [...], "spectrum": [...] }],
      "attribution": {
        "dirichlet_alpha": [50.1, 5.1, 0.1],
        "contributors": [
          { "address": "0xABC", "weight": 0.91, "raw_contribution": 50 },
          { "address": "0xDEF", "weight": 0.08, "raw_contribution": 5 },
          { "address": "0xGHI", "weight": 0.01, "raw_contribution": 0 }
        ],
        "merkle_root": "0xabc123..."
      }
    }
  ]
}
```

### Phase 5: Token Distribution

Based on CGP attribution weights, tokens are distributed:

```
token_award_i = total_pool * weight_i
```

If the weekly pool is 1000 GRO:
- Member A (weight 0.32): receives 320 GRO
- Member B (weight 0.28): receives 280 GRO
- Member C (weight 0.15): receives 150 GRO
- ... etc.

### Phase 6: Verification

Any participant can verify their attribution:

```typescript
const proof = chit.attribution.getProof(chitId);
const valid = chit.attribution.verifyProof(proof.leafHash, proof);
// Returns: true
```

---

## Contract Types

Each contract type maps to a super-node in the CGP:

### GroToken

- **Purpose**: Community currency distribution
- **Actions**: `token_received`
- **Value**: $2.00 per token (cooperative-determined)
- **Distribution**: Weekly based on Dirichlet weights

### FoodUSD

- **Purpose**: Food economy transactions
- **Actions**: `spending`
- **Categories**: groceries, prepared food, community garden
- **Benefits**: Group buying savings (5-10%)

### GroupPurchase

- **Purpose**: Collective savings through bulk buying
- **Actions**: `group_contribution`
- **Mechanism**: Pool contributions, negotiate discounts
- **Savings**: 5-10% reduction vs individual purchasing

### GroVault

- **Purpose**: Staking/lockup mechanism
- **Actions**: `staking`
- **Lock periods**: 4, 12, 26, 52 weeks
- **Reward multiplier**: 1.1x to 1.5x based on duration

### CoopGovernor

- **Purpose**: Democratic governance
- **Actions**: `voting`
- **Weight**: 1 member = 1 vote (not wealth-weighted)
- **Proposals**: Parameter changes, budget allocation

### RewardsPool

- **Purpose**: Surplus distribution
- **Actions**: `reward_claimed`
- **Source**: Group buying savings + cooperative surplus
- **Distribution**: Pro-rata based on participation weight

### LoyaltyPoints

- **Purpose**: Engagement tracking
- **Actions**: `loyalty_earned`
- **Streaks**: 4-week, 12-week, 26-week milestones
- **Bonus**: Multiplier on GroToken awards (1.1x to 1.3x)

---

## CGP Shape Attribution Flow

### From Action to Geometry

```
1. RECORD: Member action recorded with CHIT ID
                    ↓
2. EMBED: Action metadata embedded (384-dim vector)
                    ↓
3. ASSIGN: Soft assignment to constellation (via CHR)
                    ↓
4. WEIGHT: Dirichlet weight computed
                    ↓
5. PROVE: Merkle leaf created, proof generated
                    ↓
6. ENCODE: Poincare disk position computed
                    ↓
7. SPECTRUM: Energy distribution binned
                    ↓
8. PACK: CGP v1.0 packet constructed
                    ↓
9. SIGN: HMAC signature applied
                    ↓
10. EMIT: Published to tokenism.cgp.weekly.v1
```

### Geometric Interpretation

```
Poincare Disk Encoding of Week 12 Economy:

                    (0, 0)
                   Economy
                  Aggregate
                      │
          ┌───────────┼───────────┐
          │           │           │
    (0.3, 120°)  (0.3, 240°)  (0.3, 0°)
     GroToken      FoodUSD    GroupPurchase
          │           │           │
     ┌────┤      ┌────┤      ┌────┤
     │    │      │    │      │    │
    tx1  tx2    tx3  tx4    tx5  tx6
   r=0.7 r=0.8 r=0.6 r=0.9 r=0.7 r=0.8
```

- **Center (r=0)**: Total economy (aggregate)
- **First ring (r~0.3)**: Contract types (super-nodes)
- **Outer ring (r~0.7-0.9)**: Individual transactions (points)
- **Distance from center**: Specificity/granularity
- **Angular position**: Category distribution

---

## Simulation Mechanics

### Initial Conditions

| Parameter | Value | Distribution |
|-----------|-------|-------------|
| Members | 50 | Fixed |
| Initial wealth | ~$1,200 | LogNormal(mu=log(1000), sigma=0.6) |
| Weekly food budget | ~$75 | Per member |
| Membership fee | $5/week | Fixed |
| Simulation weeks | 52 | One year |

### Weekly Cycle

```
1. COLLECT membership fees ($5 × members)
2. DISTRIBUTE GroTokens based on prior week weights
3. SIMULATE spending (groceries, group purchases)
4. CALCULATE group buying savings (5-10%)
5. UPDATE Dirichlet weights with new contributions
6. COMPUTE metrics (Gini, poverty rate, wealth gap)
7. GENERATE weekly CGP
8. PUBLISH to NATS
```

### Wealth Formula

**Traditional economy:**
```
wealth_t = wealth_{t-1} + income - spending
```

**Cooperative economy:**
```
wealth_t = usd_balance + (grotoken_balance × $2.00)
         + group_buying_savings
         + local_production_benefit
         - membership_fee
```

### Random Events

The simulation includes stochastic elements:
- **Spending variance**: Normal(mean=budget, std=0.15*budget)
- **Group purchase savings**: Uniform(5%, 10%)
- **Emergency expenses**: 5% chance per member per week of 2x spending
- **Income variation**: Normal(mean=weekly_income, std=0.1*income)

---

## Fairness Metrics

### Gini Coefficient

Measures wealth inequality on a scale of 0 (perfect equality) to 1 (total inequality):

```
G = sum((2*i - n - 1) * w_i) / (n * sum(w_i))

where:
  w_i = sorted wealth values (ascending)
  n = number of members
  i = rank (1 to n)
```

| Gini Value | Interpretation | Target |
|------------|---------------|--------|
| 0.0-0.25 | Very equal | Cooperative goal |
| 0.25-0.4 | Moderate inequality | Acceptable |
| 0.4-0.6 | High inequality | Traditional economy |
| 0.6-1.0 | Extreme inequality | Crisis |

**Cooperative target: Gini < 0.4** (compared to traditional ~0.6)

### Poverty Rate

Fraction of members below the poverty line:

```
poverty_line = 4 × weekly_food_budget = 4 × $75 = $300
poverty_rate = count(wealth < $300) / total_members
```

**Cooperative target: < 10%** (compared to traditional ~25%)

### Wealth Gap Ratio

Ratio of top-20% mean wealth to bottom-20% mean wealth:

```
gap_ratio = mean(top_20%_wealth) / mean(bottom_20%_wealth)
```

**Cooperative target: < 3.0** (compared to traditional ~8.0)

### Participation Rate

Fraction of members active in the last 4 weeks:

```
participation = count(last_activity_within_4_weeks) / total_members
```

**Target: > 85%**

---

## NATS Event Integration

### Published Subjects

| Subject | Frequency | Payload |
|---------|-----------|---------|
| `tokenism.attribution.recorded.v1` | Per action | Single attribution record |
| `tokenism.cgp.weekly.v1` | Weekly | Full weekly CGP with metrics |
| `tokenism.cgp.ready.v1` | On demand | CGP ready for consumption |
| `tokenism.swarm.population.v1` | Per evolution | Swarm fitness update |
| `tokenism.geometry.event.v1` | On demand | Voice synthesis events |
| `tokenism.credential.rotated.v1` | On rotation | Credential audit event |

### Key Payloads

**Attribution Recorded:**
```json
{
  "chit_id": "chit-1a2b3c-0001",
  "address": "0xMEMBER0...",
  "action": "spending",
  "amount": 50.0,
  "week": 12,
  "category": "groceries",
  "merkle_root": "0xdef456...",
  "timestamp": "2026-03-11T12:00:00Z"
}
```

**Weekly CGP:**
```json
{
  "week": 12,
  "cgp": { "spec": "chit.cgp.v1.0", "..." : "..." },
  "super_node_count": 7,
  "total_attributions": 150,
  "gini": 0.42,
  "poverty_rate": 0.15,
  "cgp_spec": "chit.cgp.v1.0"
}
```

**Swarm Population:**
```json
{
  "namespace": "pmoves.tokenism",
  "modality": "economic_simulation",
  "pack_id": "sim-week-12",
  "status": "active",
  "population_id": "pop-uuid",
  "generation": 5,
  "best_fitness": 0.87,
  "metrics": {
    "gini": 0.38,
    "poverty_rate": 0.12,
    "total_wealth": 125000.0,
    "wealth_growth_rate": 0.05,
    "participation_rate": 0.92
  }
}
```

---

## Cooperative vs Traditional Model

### Side-by-Side Comparison

| Metric | Traditional | Cooperative | Delta |
|--------|-------------|-------------|-------|
| **Wealth Formula** | Income - Spending | USD + (GRO × $2) + savings | +Community currency |
| **Group Buying** | None | 5-10% savings | +5-10% |
| **Local Production** | None | 15% cost reduction | +15% |
| **Community Currency** | None | $2 per GroToken | +Liquidity |
| **Membership Fee** | $0 | $5/week | -$260/year |
| **Gini (after 52w)** | ~0.55-0.65 | ~0.30-0.40 | -35% inequality |
| **Poverty Rate** | ~20-30% | ~5-12% | -60% poverty |
| **Wealth Gap** | ~6-10x | ~2-4x | -50% gap |

### The Cooperative Advantage

```
Traditional:
  wealth_growth = income - expenses
  = $500/wk - $475/wk = $25/wk

Cooperative:
  wealth_growth = income - expenses + coop_benefits
  = $500/wk - $475/wk + group_savings + gro_tokens + local_production
  = $25/wk + $25/wk + $20/wk + $15/wk = $85/wk

  3.4x wealth growth rate
```

### What Makes It Work

1. **Group buying power**: 50 members buying together vs individually
2. **Community currency**: GroTokens create local liquidity
3. **Local production**: Reduced costs through cooperative production
4. **Geometric fairness**: Dirichlet guarantees prevent wealth concentration
5. **Transparent accounting**: CGP-encoded attribution is publicly verifiable
6. **Evolutionary optimization**: EvoSwarm continuously improves fairness parameters

---

## Cross-References

### Technical Implementation
- [TOKENISM_DEVELOPER_GUIDE.md](TOKENISM_DEVELOPER_GUIDE.md) — 8 TS module reference + service integration
- [MATH_PIPELINE_WALKTHROUGH.md](PMOVESCHIT/MATH_PIPELINE_WALKTHROUGH.md) — Complete encoding pipeline
- [CGP_ENCODING_REFERENCE.md](PMOVESCHIT/CGP_ENCODING_REFERENCE.md) — CGP field construction
- [CALIBRATION_GUIDE.md](PMOVESCHIT/CALIBRATION_GUIDE.md) — Encoding calibration procedures

### Platform Integration
- [CHIT_INTEGRATION_STATUS.md](audit/CHIT_INTEGRATION_STATUS.md) — Per-service CHIT integration
- [geometry-nats-subjects.md](../.claude/context/geometry-nats-subjects.md) — NATS subjects
- [EVOSWARM_OPERATIONS_GUIDE.md](EVOSWARM_OPERATIONS_GUIDE.md) — Parameter optimization

### Vision & Business
- [CATACLYSM_CROSSLINKS.md](CATACLYSM_CROSSLINKS.md) — Business vision bridge
- [CATACLYSM_STUDIOS_INC.md](PMOVESCHIT/CATACLYSM_STUDIOS_INC.md) — Cataclysm vision
- [Human_side.md](PMOVESCHIT/Human_side.md) — User-facing documentation

---

*This document is a living artifact tracked by [CHIT_CHANGE_TRACKER.md](CHIT_CHANGE_TRACKER.md).*
