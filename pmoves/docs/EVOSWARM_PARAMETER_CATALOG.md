# EvoSwarm Parameter Catalog

**Layer:** L1 Protocol / L3 Applied
**Status:** Current
**Last Updated:** 2026-03-11

> Complete reference for the EvoSwarm parameter genome — all tunable parameters for CGP encoding, decoding, and energy optimization with defaults and safe ranges.

---

## Table of Contents

1. [Parameter Genome Overview](#parameter-genome-overview)
2. [CG Builder Genome](#cg-builder-genome)
3. [Decoder Genome](#decoder-genome)
4. [Energy Genome](#energy-genome)
5. [Parameter Pack Schema](#parameter-pack-schema)
6. [Safe Ranges](#safe-ranges)
7. [Cross-References](#cross-references)

---

## Parameter Genome Overview

The EvoSwarm parameter genome has three sections:

```json
{
  "cg_builder": { ... },   // Controls CGP encoding (CHR algorithm)
  "decoder": { ... },      // Controls CGP decoding and reconstruction
  "energy": { ... }        // Tracks energy/performance metrics
}
```

Each section evolves independently via genetic operators (crossover, mutation) within defined safe ranges.

---

## CG Builder Genome

Controls how content is encoded into Constellation Geometry.

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `K` | integer | 8 | 4-16 | Number of constellations |
| `bins` | integer | 8 | 5-12 | Spectrum histogram resolution |
| `tau` | float | 0.1 | 0.01-1.0 | Softmax temperature for assignment |
| `beta` | float | 0.01 | 0-0.1 | Regularization weight (prevents anchor collapse) |
| `spectrum_mode` | enum | `"fft"` | fft, wavelet, hybrid | Spectrum computation transform |
| `mf_rank` | integer | 32 | 8-128 | Matrix factorization rank (optional) |

### Parameter Effects

**K (Constellations)**
- Lower K (4-6): Coarse clustering, fast encoding, potential topic mixing
- Higher K (10-16): Fine-grained clustering, slower encoding, potential fragmentation
- Rule of thumb: `K ~ sqrt(N / 10)` where N = content units

**bins (Spectrum Resolution)**
- Lower bins (5-6): Smooth spectra, less discriminative
- Higher bins (10-12): Detailed spectra, more data per constellation
- Default 8 works for most use cases

**tau (Temperature)**
- Lower tau (0.01-0.05): Hard assignment (each unit goes to one constellation)
- Higher tau (0.5-1.0): Soft assignment (units spread across constellations)
- Default 0.1 gives mostly hard assignments with some softness

**beta (Regularization)**
- beta = 0: No regularization, anchors may collapse to same direction
- beta = 0.1: Strong regularization, anchors stay well-separated
- Default 0.01 provides light regularization

**spectrum_mode**
- `fft`: Standard Fourier transform (fastest, most common)
- `wavelet`: Multi-resolution analysis (better for heterogeneous content)
- `hybrid`: Combined FFT + wavelet (best quality, slowest)

### Example

```json
{
  "cg_builder": {
    "K": 8,
    "bins": 8,
    "tau": 0.1,
    "beta": 0.01,
    "spectrum_mode": "fft",
    "mf_rank": 32
  }
}
```

---

## Decoder Genome

Controls how CGP geometry is decoded back to content.

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `mode` | enum | `"swarm"` | swarm, hrm, direct | Decoding strategy |
| `hrm_halt_thresh` | float | 0.95 | 0.8-0.99 | HRM refinement stopping threshold |
| `hrm_mmax` | integer | 5 | 1-10 | Max HRM iterations |
| `gan_weight` | float | 0.3 | 0-1.0 | GAN sidecar influence weight |

### Decoding Modes

**direct**
- Simplest mode: direct projection matching
- Fastest but lowest quality
- Use for: real-time applications, low-latency requirements

**hrm (Hierarchical Refinement Model)**
- Iterative refinement: coarse → fine matching
- Medium speed, good quality
- Parameters: `hrm_halt_thresh` (when to stop), `hrm_mmax` (max iterations)
- Use for: balanced quality/speed

**swarm**
- Evolutionary search over reconstruction candidates
- Slowest but highest quality
- Uses `gan_weight` for adversarial quality scoring
- Use for: offline processing, archival quality

### Parameter Effects

**hrm_halt_thresh**
- Higher (0.95-0.99): More iterations, higher quality, slower
- Lower (0.8-0.9): Fewer iterations, faster, may miss details

**hrm_mmax**
- Higher (8-10): Allows more refinement passes
- Lower (1-3): Quick refinement, less polishing

**gan_weight**
- 0: No adversarial scoring (pure geometry matching)
- 0.3: Light adversarial (default)
- 0.8-1.0: Heavy adversarial (may hallucinate)

### Example

```json
{
  "decoder": {
    "mode": "swarm",
    "hrm_halt_thresh": 0.95,
    "hrm_mmax": 5,
    "gan_weight": 0.3
  }
}
```

---

## Energy Genome

Tracks energy and performance metrics for each parameter configuration. Not directly evolved — recorded as fitness metadata.

| Parameter | Type | Unit | Description |
|-----------|------|------|-------------|
| `nvml_avg_watts` | float | Watts | Average GPU power consumption |
| `duration_ms` | integer | Milliseconds | Encoding/decoding duration |
| `quality_score` | float | [0, 1] | Reconstruction quality metric |

### Energy-Aware Fitness

When NVML is enabled (`NVML_ENABLED=true`), fitness includes an energy penalty:

```
energy_penalty = nvml_avg_watts * duration_ms / 1000  // Watt-seconds (Joules)
adjusted_fitness = base_fitness - (energy_weight * normalized_energy)
```

This drives evolution toward **energy-efficient** parameter configurations.

### Example

```json
{
  "energy": {
    "nvml_avg_watts": 250.0,
    "duration_ms": 1234,
    "quality_score": 0.92
  }
}
```

---

## Parameter Pack Schema

A complete parameter pack as stored in Supabase and published to NATS:

```json
{
  "pack_id": "pack-12345",
  "timestamp": "2026-03-11T12:00:00Z",
  "population_id": "pop-67",
  "namespace": "default",
  "status": "active",
  "best_fitness": 0.94,
  "parameters": {
    "cg_builder": {
      "K": 8,
      "bins": 8,
      "tau": 0.1,
      "beta": 0.01,
      "spectrum_mode": "fft",
      "mf_rank": 32
    },
    "decoder": {
      "mode": "swarm",
      "hrm_halt_thresh": 0.95,
      "hrm_mmax": 5,
      "gan_weight": 0.3
    }
  },
  "energy": {
    "nvml_avg_watts": 250.0,
    "duration_ms": 1234,
    "quality_score": 0.92
  },
  "provenance": {
    "controller_version": "0.1.0",
    "sample_size": 25,
    "evolution_cycles": 42,
    "parent_pack_ids": ["pack-12340", "pack-12338"]
  }
}
```

### Status Values

| Status | Description |
|--------|-------------|
| `testing` | New pack, being evaluated |
| `active` | Current best, consumed by services |
| `archived` | Superseded by better pack |

### JSON Schema

Location: `pmoves/contracts/schemas/geometry/swarm.meta.v1.schema.json`

---

## Safe Ranges

**Hard limits** — values outside these ranges will be rejected:

| Parameter | Minimum | Maximum | Reason |
|-----------|---------|---------|--------|
| `K` | 2 | 32 | < 2 is degenerate, > 32 is fragmented |
| `bins` | 3 | 20 | < 3 loses information, > 20 is noise |
| `tau` | 0.001 | 10.0 | < 0.001 is degenerate hard, > 10 is uniform |
| `beta` | 0 | 1.0 | > 1.0 dominates reconstruction loss |
| `hrm_halt_thresh` | 0.5 | 0.999 | < 0.5 is too early, > 0.999 never converges |
| `hrm_mmax` | 1 | 50 | > 50 is wasteful |
| `gan_weight` | 0 | 1.0 | Weight fraction |

**Soft limits** — values outside these ranges trigger warnings:

| Parameter | Soft Min | Soft Max | Warning |
|-----------|----------|----------|---------|
| `K` | 4 | 16 | "Unusual K value, may affect quality" |
| `bins` | 5 | 12 | "Unusual bins value, verify calibration" |
| `tau` | 0.01 | 1.0 | "Extreme temperature, check assignments" |
| `mf_rank` | 8 | 128 | "Unusual rank, may affect memory" |

### Mutation Ranges

During evolution, mutation is bounded to prevent wild parameter jumps:

```
mutated_value = current_value + gaussian(0, sigma)
sigma = mutation_rate * (soft_max - soft_min)
mutation_rate = 0.1 (default)
```

Clipped to hard limits after mutation.

---

## Cross-References

- [EVOSWARM_OPERATIONS_GUIDE.md](EVOSWARM_OPERATIONS_GUIDE.md) — EvoSwarm operations
- [AGENTGYM_RL_OPERATIONS.md](AGENTGYM_RL_OPERATIONS.md) — Training operations
- [CALIBRATION_GUIDE.md](PMOVESCHIT/CALIBRATION_GUIDE.md) — CGP calibration
- [CGP_ENCODING_REFERENCE.md](PMOVESCHIT/CGP_ENCODING_REFERENCE.md) — CGP field reference
- [swarm.meta.v1.schema.json](../contracts/schemas/geometry/swarm.meta.v1.schema.json) — JSON Schema

---

*This document is a living artifact tracked by [CHIT_CHANGE_TRACKER.md](CHIT_CHANGE_TRACKER.md).*
