# CHIT Calibration Guide

**Layer:** L1 Protocol / L3 Applied
**Status:** Current
**Last Updated:** 2026-03-11

> Procedures for calibrating CHIT encoding/decoding quality using KL divergence, JS divergence, Wasserstein distance, and coverage metrics. Includes codebook sandboxing, parameter tuning, and troubleshooting.

---

## Table of Contents

1. [Overview](#overview)
2. [Calibration Metrics](#calibration-metrics)
3. [Baseline Calibration](#baseline-calibration)
4. [Codebook Sandboxing](#codebook-sandboxing)
5. [Parameter Tuning](#parameter-tuning)
6. [Monitoring & Alerts](#monitoring--alerts)
7. [Troubleshooting](#troubleshooting)
8. [Cross-References](#cross-references)

---

## Overview

Calibration ensures that CGP packets accurately represent their source content and can be faithfully decoded. The key question is: **does the decoded output match the original?**

### When to Calibrate

| Trigger | Action |
|---------|--------|
| New embedding model deployed | Full recalibration |
| K or bins changed | Spectrum recalibration |
| Corpus significantly updated | Codebook refresh |
| Metrics drift detected | Incremental tuning |
| New content modality added | Modality-specific calibration |

### Calibration Pipeline

```
Encode → Decode → Compare → Metrics → Adjust → Re-encode
  ↑                                                  │
  └──────────────────────────────────────────────────┘
```

---

## Calibration Metrics

### KL Divergence (Kullback-Leibler)

Measures how the decoded spectrum diverges from the encoded spectrum:

```
KL(P || Q) = sum(P[i] * log(P[i] / Q[i]))

where:
  P = encoded spectrum (target)
  Q = decoded spectrum (reconstructed)
```

| KL Value | Quality | Action |
|----------|---------|--------|
| < 0.1 | Excellent | No action needed |
| 0.1 - 0.3 | Good | Acceptable for production |
| 0.3 - 0.5 | Fair | Consider tuning |
| > 0.5 | Poor | Recalibration required |

**Important**: KL divergence is asymmetric. Always compute KL(encoded || decoded), not the reverse.

### JS Divergence (Jensen-Shannon)

Symmetric version of KL, bounded [0, 1]:

```
JS(P, Q) = 0.5 * KL(P || M) + 0.5 * KL(Q || M)
where M = 0.5 * (P + Q)
```

| JS Value | Quality | Action |
|----------|---------|--------|
| < 0.05 | Excellent | No action |
| 0.05 - 0.15 | Good | Acceptable |
| 0.15 - 0.3 | Fair | Tune parameters |
| > 0.3 | Poor | Recalibrate |

### Wasserstein-1D (Earth Mover's Distance)

Measures the minimum "work" to transform one distribution into another:

```
W1(P, Q) = integral(|CDF_P(x) - CDF_Q(x)| dx)
```

More robust to small shifts than KL/JS. Useful when spectra are close but slightly offset.

| W1 Value | Quality |
|----------|---------|
| < 0.1 | Excellent |
| 0.1 - 0.2 | Good |
| > 0.2 | Needs attention |

### Coverage

Fraction of original content units successfully recovered by the decoder:

```
coverage = |decoded_units intersect original_units| / |original_units|
```

| Coverage | Quality |
|----------|---------|
| > 0.9 | Excellent |
| 0.8 - 0.9 | Good |
| 0.6 - 0.8 | Fair (geometry-only mode expected) |
| < 0.6 | Poor |

---

## Baseline Calibration

### Step 1: Prepare Calibration Corpus

```python
# Use a representative corpus (1000-5000 units)
corpus_texts = load_corpus("calibration_set.jsonl")
corpus_vecs = model.encode(corpus_texts, normalize_embeddings=True)
```

Requirements:
- **Representative**: Same domain/style as production content
- **Diverse**: Covers the full semantic range expected
- **Labeled**: Ground-truth topics/categories known (if possible)
- **Size**: 1000-5000 units for reliable statistics

### Step 2: Encode

```python
from pmoves.tools.chr import ConstellationHarvest

chr = ConstellationHarvest(K=8, bins=8)
U = chr.optimize_anchors(corpus_vecs)
p = chr.compute_assignments(corpus_vecs, U)
spectra = chr.compute_spectra(corpus_vecs, U, p, bins=8)
cgp = build_cgp(U, spectra, corpus_vecs, corpus_texts, meta={...})
```

### Step 3: Decode

```python
from pmoves.tools.chit.chit_decoder import decode_geometry

decoded = decode_geometry(
    cgp=cgp,
    corpus_texts=corpus_texts,
    corpus_vecs=corpus_vecs,
    top_k=10  # candidates per constellation
)
```

### Step 4: Measure

```python
from pmoves.tools.chit.chit_decoder import compute_metrics

metrics = compute_metrics(
    cgp=cgp,
    decoded=decoded,
    corpus_texts=corpus_texts,
    corpus_vecs=corpus_vecs
)

print(f"Mean KL:       {metrics['mean']['KL']:.4f}")
print(f"Mean JS:       {metrics['mean']['JS']:.4f}")
print(f"Mean W1:       {metrics['mean']['W1']:.4f}")
print(f"Mean Coverage: {metrics['mean']['coverage']:.3f}")
print(f"Per-constellation KL: {metrics['per_constellation']['KL']}")
```

### Step 5: Record Baseline

```json
{
  "calibration_id": "cal-2026-03-11",
  "backend": "sentence-transformers/all-MiniLM-L6-v2",
  "K": 8,
  "bins": 8,
  "corpus_size": 3000,
  "metrics": {
    "mean_KL": 0.18,
    "mean_JS": 0.08,
    "mean_W1": 0.12,
    "mean_coverage": 0.87
  },
  "per_constellation": [
    {"id": "const_0_0", "KL": 0.12, "coverage": 0.92},
    {"id": "const_0_1", "KL": 0.25, "coverage": 0.81}
  ]
}
```

---

## Codebook Sandboxing

The **Universal Codebook Property** requires that encoder and decoder share the same embedding model and corpus. When the corpus changes, the codebook must be refreshed.

### What is a Codebook?

A codebook is the decoder's reference corpus — the set of (text, embedding) pairs used to reconstruct content from geometric coordinates.

### Sandboxing Strategy

```
Production Codebook
  └── Sandbox A (new content added)
  └── Sandbox B (different K/bins)
  └── Sandbox C (different model)
```

### Creating a Sandbox

```python
# Fork the production codebook
sandbox = ProductionCodebook.fork("sandbox-A")

# Add new content
sandbox.add_texts(new_texts, model)

# Calibrate against known CGPs
metrics = sandbox.calibrate(reference_cgps)

# Promote if metrics pass
if metrics["mean_KL"] < 0.3 and metrics["mean_coverage"] > 0.8:
    sandbox.promote_to_production()
```

### Codebook Refresh Schedule

| Trigger | Frequency | Impact |
|---------|-----------|--------|
| New content ingested | Weekly | Low (incremental add) |
| Model version change | On deploy | High (full rebuild) |
| K/bins change | On config change | Medium (re-encode) |
| Quality drift > 20% | On detection | High (investigate root cause) |

---

## Parameter Tuning

### K (Number of Constellations)

| Symptom | Diagnosis | Fix |
|---------|-----------|-----|
| High KL on all constellations | K too low, mixed topics | Increase K |
| Many near-empty constellations | K too high | Decrease K |
| One constellation has most points | Unbalanced assignment | Adjust tau or increase K |

**Rule of thumb**: `K ~ sqrt(N / 10)` where N = number of content units.

### bins (Spectrum Resolution)

| Symptom | Diagnosis | Fix |
|---------|-----------|-----|
| Spectra look flat/uniform | bins too low | Increase bins |
| Spectra look noisy/spiky | bins too high | Decrease bins |
| W1 high but KL low | Binning artifacts | Try adjacent bin counts |

**Rule of thumb**: 8 bins works for most use cases. Use 5-6 for < 100 units, 10-12 for > 5000 units.

### tau (Temperature)

| Symptom | Diagnosis | Fix |
|---------|-----------|-----|
| All points assigned to one constellation | tau too low | Increase tau |
| Assignments nearly uniform | tau too high | Decrease tau |
| Good separation but some outliers | tau is fine | Consider removing outliers |

**Range**: 0.01 (hard assignment) to 1.0 (soft/uniform). Default: 0.1.

### Zeta Filter Parameters

| Parameter | Effect of Increase | Effect of Decrease |
|-----------|-------------------|-------------------|
| `numZeros` | More harmonics, smoother filtering | Fewer harmonics, sharper filtering |
| `decayFactor` | Higher zeros contribute more | Focus on lowest zeros |

**Recommended**: numZeros=10, decayFactor=0.9 for general text. Use numZeros=5 for short documents.

---

## Monitoring & Alerts

### Prometheus Metrics

Services publishing CGPs should expose:

```python
# In your service metrics
cgp_kl_divergence = Histogram(
    'cgp_kl_divergence',
    'KL divergence of CGP encoding',
    buckets=[0.05, 0.1, 0.2, 0.3, 0.5, 1.0]
)

cgp_coverage = Histogram(
    'cgp_coverage',
    'Coverage of CGP decoding',
    buckets=[0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 1.0]
)
```

### Alert Thresholds

```yaml
# Grafana alert rules
- alert: CGPQualityDegraded
  expr: histogram_quantile(0.5, cgp_kl_divergence_bucket) > 0.5
  for: 1h
  labels:
    severity: warning
  annotations:
    summary: "CGP encoding quality degraded (median KL > 0.5)"

- alert: CGPCoverageLow
  expr: histogram_quantile(0.5, cgp_coverage_bucket) < 0.7
  for: 1h
  labels:
    severity: critical
  annotations:
    summary: "CGP decoding coverage below 70%"
```

### NATS Telemetry

Calibration results are published to `geometry.cgp.calibration.v1`:

```json
{
  "calibration_id": "cal-2026-03-11",
  "timestamp": "2026-03-11T12:00:00Z",
  "metrics": {
    "mean_KL": 0.18,
    "mean_coverage": 0.87
  },
  "status": "healthy"
}
```

EvoSwarm consumes this telemetry to drive parameter evolution.

---

## Troubleshooting

### High KL Divergence (> 0.5)

**Causes:**
1. **Model mismatch**: Encoder and decoder using different embedding models
2. **Corpus drift**: Production content differs significantly from calibration corpus
3. **Parameter mismatch**: K/bins changed without recalibration
4. **Anchor collapse**: Multiple anchors converged to similar directions

**Diagnosis:**
```python
# Check per-constellation KL
for k, kl in enumerate(metrics["per_constellation"]["KL"]):
    if kl > 0.5:
        print(f"Constellation {k}: KL={kl:.4f} — investigate anchor quality")

# Check anchor similarity
for i in range(K):
    for j in range(i+1, K):
        sim = np.dot(U[i], U[j])
        if sim > 0.9:
            print(f"Anchors {i},{j} too similar (cos={sim:.3f})")
```

### Low Coverage (< 0.7)

**Causes:**
1. **Missing corpus items**: New content not in decoder's codebook
2. **Projection bounds too tight**: `radial_minmax` excludes valid projections
3. **top_k too low**: Not enough candidates considered
4. **Domain shift**: Content from a new domain not covered by corpus

**Fix:**
```python
# Increase top_k
decoded = decode_geometry(cgp, corpus_texts, corpus_vecs, top_k=50)

# Check for uncovered regions
uncovered = set(range(len(corpus_texts))) - set(decoded_indices)
print(f"Uncovered units: {len(uncovered)} / {len(corpus_texts)}")
```

### Entropy Trajectory Not Converging

If `Hg_traj` doesn't decrease or `Hs_traj` collapses to near-zero:

```python
# Check iteration count
if len(Hg_traj) < 50:
    print("Increase max_iter (current may be insufficient)")

# Check beta regularization
if Hs_traj[-1] < 0.01:
    print("Increase beta to prevent anchor collapse")
```

### Zeta Filter Distortion

If `spectrum_zeta` looks very different from `spectrum`:

```python
# Compare filtered vs raw
for k in range(K):
    delta = np.abs(np.array(spectra_zeta[k]) - np.array(spectra[k]))
    if delta.max() > 0.2:
        print(f"Constellation {k}: zeta distortion too high, reduce numZeros")
```

---

## Cross-References

- [MATH_PIPELINE_WALKTHROUGH.md](MATH_PIPELINE_WALKTHROUGH.md) — Complete pipeline narrative
- [CGP_ENCODING_REFERENCE.md](CGP_ENCODING_REFERENCE.md) — Field-by-field packet construction
- [CGP_v1.0_SPECIFICATION.md](CGP_v1.0_SPECIFICATION.md) — Official wire format spec
- [EVOSWARM_OPERATIONS_GUIDE.md](../EVOSWARM_OPERATIONS_GUIDE.md) — Parameter pack optimization
- [CHIT Tools Catalog](../CHIT_TOOLS_CATALOG.md) — Python tooling reference

---

*This document is a living artifact tracked by [CHIT_CHANGE_TRACKER.md](../CHIT_CHANGE_TRACKER.md).*
