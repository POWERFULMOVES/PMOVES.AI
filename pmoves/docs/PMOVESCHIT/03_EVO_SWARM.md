# EVO SWARM

*Distributed optimization without a central authority.*

> **Previously:** [The GEOMETRY BUS](02_GEOMETRY_BUS.md) explained how CGP packets flow between services. This document explains how the attribution weights inside those packets are optimized for fairness.

---

## What It Does

When multiple contributors create content that gets encoded into a CGP, someone has to decide how much credit each contributor deserves. A centralized authority could assign weights — but that creates a single point of failure and trust.

EVO SWARM solves this with an evolutionary algorithm: a population of agents each propose attribution weights, compete on a fairness-based fitness function, and converge on a consensus — no central coordinator, no backpropagation, no gradient descent.

The analogy: imagine a cooperative where members vote on fair revenue splits. Bad proposals (unfair distributions) die off over generations. Good proposals (balanced, inclusive distributions) survive and reproduce. After enough rounds, the population converges on splits that most members agree are fair.

---

## The Evolutionary Loop

```
┌─────────────────────────────────────────────────────┐
│                                                     │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐        │
│  │Population│──▶│ Mutation  │──▶│Crossover │        │
│  │ (agents) │   │(Dirichlet│   │(recombine│        │
│  │          │   │  noise)  │   │ vectors) │        │
│  └──────────┘   └──────────┘   └─────┬────┘        │
│       ▲                              │              │
│       │         ┌──────────┐   ┌─────▼────┐        │
│       └─────────│Selection │◀──│ Fitness  │        │
│                 │(top-K by │   │ scoring  │        │
│                 │ fitness) │   │          │        │
│                 └──────────┘   └──────────┘        │
│                                                     │
└─── repeat until convergence ────────────────────────┘
```

### 1. Population

Each agent in the swarm holds a weight vector: one weight per contributor, summing to 1.0. The initial population is seeded from a Dirichlet distribution with uniform priors (all alphas = 1), ensuring a diverse starting set.

### 2. Mutation

Each generation, agents perturb their weight vectors by adding Dirichlet noise:

```
weights' = normalize(weights + Dir(alpha_noise))
```

The noise concentration parameter controls exploration: low alpha means wild mutations (exploring new weight territories), high alpha means conservative tweaks (refining near the current best).

### 3. Crossover

Pairs of agents exchange portions of their weight vectors to produce offspring. This combines good traits from different proposals — one agent might have fair weights for contributor A, another for contributor B.

### 4. Fitness Scoring

Each agent's weight vector is scored by a composite fitness function:

```
fitness = -H_posterior + lambda * fairness_penalty
```

Where:
- `H_posterior` = entropy after applying weights (lower entropy = more decisive attribution)
- `fairness_penalty` = penalizes extreme inequality (high Gini, high poverty rate)

An agent that gives all credit to one contributor scores poorly (unfair). An agent that spreads credit evenly but randomly also scores poorly (high entropy, no signal). The best fitness comes from *decisive but fair* allocations.

### 5. Selection

The top-K agents by fitness survive to the next generation. The rest are replaced by offspring from the survivors.

---

## Cooperative Metrics

EVO SWARM tracks four key metrics to ensure the attribution converges on fair outcomes:

| Metric | Target | Meaning |
|--------|--------|---------|
| **Gini Coefficient** | < 0.30 | Wealth/credit inequality. 0 = perfect equality, 1 = one agent gets everything. |
| **Poverty Rate** | < 10% | Percentage of contributors receiving less than a minimum threshold of credit. |
| **Participation Rate** | > 70% | Percentage of eligible contributors with non-trivial weight (above noise floor). |
| **Fitness** | Composite | The evolutionary fitness of the best agent in the current generation. |

These metrics are published to NATS on `tokenism.swarm.population.v1` after each generation, allowing dashboards and analytics to track convergence in real time.

---

## How It Connects

EVO SWARM does not operate in isolation. It is part of the CHIT feedback loop:

1. **Input:** EVO SWARM reads CGP attribution data — the Dirichlet alphas and contributor weights from incoming packets on the GEOMETRY BUS.
2. **Optimization:** It runs the evolutionary loop to find fairer weight distributions.
3. **Output:** Updated weights are published back to the GEOMETRY BUS via `tokenism.swarm.population.v1` and `geometry.swarm.meta.v1`.
4. **Feedback:** The optimized Dirichlet parameters feed back into the next CGP encoding cycle, producing better-calibrated spectra and more equitable attribution in subsequent packets.

---

## Implementation

| Component | Location | Language |
|-----------|----------|----------|
| Core algorithm | `PMOVES-ToKenism-Multi/integrations/contracts/chit/swarm-attribution.ts` | TypeScript |
| NATS publishing | `PMOVES-ToKenism-Multi/integrations/contracts/chit/chit-nats-publisher.ts` | TypeScript |
| Population updates | Subject: `tokenism.swarm.population.v1` | NATS |
| Swarm metadata | Subject: `geometry.swarm.meta.v1` | NATS |

For the CGP specification of the EVO SWARM fields, see [CGP_v1.0_SPECIFICATION.md](CGP_v1.0_SPECIFICATION.md) § Swarm Optimization.

---

## Full Circle

The three acts of CHIT form a closed loop:

```
   CHIT encodes meaning ──▶ Bus transports shapes ──▶ Swarm optimizes fairness
         │                                                      │
         └──────────── better shapes next cycle ◀───────────────┘
```

1. **CHIT** encodes information as geometric constellations (anchors + spectra).
2. **GEOMETRY BUS** carries those packets between services via NATS.
3. **EVO SWARM** optimizes the attribution weights for fairness and decisiveness.
4. The optimized weights feed back into the Dirichlet priors for the *next* encoding cycle, producing higher-quality CGPs.

Each cycle, the system gets better at representing meaning, transporting it faithfully, and crediting contributors fairly.

---

**See also:** [Glossary](00_GLOSSARY.md) · [CGP v1.0 Specification](CGP_v1.0_SPECIFICATION.md) · [GEOMETRY BUS](02_GEOMETRY_BUS.md) · [Back to README](README.md)
