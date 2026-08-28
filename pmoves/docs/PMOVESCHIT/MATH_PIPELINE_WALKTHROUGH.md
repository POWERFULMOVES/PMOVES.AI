# CHIT Mathematical Pipeline Walkthrough

**Layer:** L1 Protocol / L2 Conceptual
**Status:** Current
**Last Updated:** 2026-03-11

> End-to-end walkthrough of the CHIT mathematical encoding pipeline: from raw content through Dirichlet attribution, hyperbolic embedding, zeta spectral filtering, to CGP packet construction, transport, and decoding.

---

## Table of Contents

1. [Pipeline Overview](#pipeline-overview)
2. [Stage 1: Content Ingestion & Embedding](#stage-1-content-ingestion--embedding)
3. [Stage 2: Constellation Harvest Regularization (CHR)](#stage-2-constellation-harvest-regularization-chr)
4. [Stage 3: Dirichlet Attribution Weighting](#stage-3-dirichlet-attribution-weighting)
5. [Stage 4: Hyperbolic Geometry Encoding](#stage-4-hyperbolic-geometry-encoding)
6. [Stage 5: Zeta Spectral Filtering](#stage-5-zeta-spectral-filtering)
7. [Stage 6: CGP Packet Construction](#stage-6-cgp-packet-construction)
8. [Stage 7: Security (Signing & Encryption)](#stage-7-security-signing--encryption)
9. [Stage 8: Transport (GEOMETRY BUS)](#stage-8-transport-geometry-bus)
10. [Stage 9: Decoding & Reconstruction](#stage-9-decoding--reconstruction)
11. [Stage 10: Swarm Optimization Feedback](#stage-10-swarm-optimization-feedback)
12. [Complete Data Flow Diagram](#complete-data-flow-diagram)
13. [Cross-References](#cross-references)

---

## Pipeline Overview

The CHIT (Cymatic Holographic Information Theory) pipeline transforms arbitrary content into **boundary representations** — geometric packets called CGPs (CHIT Geometry Packets) — that encode meaning as constellations of anchors, spectra, and attribution proofs rather than raw token streams.

### Why Geometry Instead of Tokens?

| Property | Token Stream | CGP Geometry |
|----------|-------------|--------------|
| **Compression** | Linear with content length | Logarithmic (boundary representation) |
| **Translatability** | Language-specific | Universal (geometric invariants) |
| **Attribution** | Lost after generation | Merkle-proven per contributor |
| **Privacy** | Content visible | Anchors can be encrypted (AES-GCM) |
| **Decodability** | Direct | Codebook-reconstructible or exact |

### The Five Mathematical Pillars

| Pillar | Mathematical Basis | Role in Pipeline |
|--------|-------------------|------------------|
| **Dirichlet Distributions** | Bayesian conjugate priors | Fair contribution weighting |
| **Hyperbolic Geometry** | Poincare disk (K = -1) | Hierarchical spatial encoding |
| **Zeta Spectral Filtering** | Riemann zeta zeros (gamma_k) | Signal enhancement via prime resonance |
| **Merkle Proofs** | Hash-based verification trees | Tamper-proof attribution chains |
| **Swarm Optimization** | Evolutionary algorithms | Distributed parameter consensus |

### Pipeline Stages at a Glance

```
Content → Embed → CHR → Dirichlet → Hyperbolic → Zeta → CGP → Sign → NATS → Decode
  (1)     (1)    (2)      (3)         (4)        (5)   (6)   (7)    (8)     (9)
                                                                              ↑
                                                              Swarm Feedback (10)
```

---

## Stage 1: Content Ingestion & Embedding

### Input Types

The pipeline accepts six content modalities:

| Source | units_mode | Embedding Model | Example |
|--------|-----------|----------------|---------|
| `text` | `sentences` or `paragraphs` | all-MiniLM-L6-v2 | Documents, transcripts |
| `docx` | `paragraphs` | all-MiniLM-L6-v2 | Word documents |
| `image` | `frames` | CLIP ViT-B-32 | Photos, screenshots |
| `audio` | `samples` | Whisper + embedding | Podcasts, music |
| `video` | `frames` | CLIP + temporal | YouTube, streams |
| `latent` | `tokens` | Pre-embedded vectors | Agent reasoning traces |

### Embedding Process

```python
from sentence_transformers import SentenceTransformer

model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')

# 1. Split content into units
units = split_into_sentences(document)  # or paragraphs, frames, etc.

# 2. Generate normalized embeddings
embeddings = model.encode(
    units,
    normalize_embeddings=True,  # L2 norm = 1.0 (critical for projection)
    show_progress_bar=True
)
# Shape: (N, 384) where N = number of units, 384 = embedding dimension
```

### Key Properties

- **Normalization**: All embeddings are L2-normalized to unit vectors. This is critical because later stages (projection, spectrum computation) assume `||v|| = 1`.
- **Dimensionality**: MiniLM-L6-v2 produces 384-dimensional vectors. CLIP ViT-B-32 produces 512-dimensional vectors.
- **Determinism**: Same input text always produces the same embedding (no temperature/sampling).

---

## Stage 2: Constellation Harvest Regularization (CHR)

CHR is the core algorithm that discovers **constellations** — clusters of semantically related content units arranged around **anchor vectors** in embedding space.

### What CHR Produces

| Output | Shape | Description |
|--------|-------|-------------|
| **Anchors (U)** | (K, D) | K unit vectors in D-dimensional space |
| **Assignments (p)** | (N, K) | Soft assignment probabilities per unit |
| **Spectra** | (K, bins) | Energy distribution per constellation |
| **Entropy trajectories** | (iterations,) | Convergence tracking |

### Algorithm Overview

```python
from pmoves.tools.chr import ConstellationHarvest

chr = ConstellationHarvest(K=8, bins=8)

# Step 2a: Optimize anchors via alternating minimization
U = chr.optimize_anchors(embeddings)
# U[k] is the "centroid direction" of constellation k
# Each anchor is a unit vector (||U[k]|| = 1)

# Step 2b: Compute soft assignments
p = chr.compute_assignments(embeddings, U)
# p[i][k] = probability that unit i belongs to constellation k
# Uses softmax over cosine similarities with temperature tau

# Step 2c: Compute energy spectra
spectra = chr.compute_spectra(embeddings, U, p, bins=8)
# spectra[k] = histogram of projections onto anchor U[k]
# Each spectrum sums to 1.0 (probability distribution)

# Step 2d: Track convergence
Hg_traj, Hs_traj = chr.compute_entropy_trajectory(embeddings, U, p)
# Hg = global entropy (should decrease toward convergence)
# Hs = slab entropy (per-constellation spread)
```

### Anchor Optimization

Anchors are found by minimizing reconstruction error:

```
minimize  sum_k sum_i  p[i][k] * (1 - cos(embedding[i], U[k]))
subject to  ||U[k]|| = 1  for all k
```

This is equivalent to **spherical k-means** with soft assignments. The alternating minimization:

1. **E-step**: Fix anchors, update assignments via softmax
2. **M-step**: Fix assignments, update anchors via weighted mean + normalize

### Spectrum Computation

For each constellation k:

1. Project all assigned units onto anchor: `proj[i] = dot(embedding[i], U[k])`
2. Scale projections to [0, 1] using `radial_minmax`
3. Bin into histogram with `bins` buckets
4. Normalize to sum = 1.0

The spectrum is the **energy fingerprint** of a constellation — it captures how the content distributes along the anchor direction.

### Configuration Parameters

| Parameter | Default | Range | Effect |
|-----------|---------|-------|--------|
| `K` | 8 | 4-16 | Number of constellations (too few = coarse, too many = noisy) |
| `bins` | 8 | 5-12 | Spectrum resolution (higher = more detail, more data) |
| `tau` | 0.1 | 0.01-1.0 | Temperature for soft assignment (lower = harder assignment) |
| `beta` | 0.01 | 0-0.1 | Regularization weight (prevents anchor collapse) |
| `max_iter` | 100 | 50-500 | Optimization iterations |

### Convergence Metrics

- **MHEP (Multi-scale Hyperbolic Entropy Product)**: `Hg * Hs` — lower is better
- **Hg trajectory**: Global entropy should monotonically decrease
- **Hs trajectory**: Slab entropy should stabilize (not collapse to 0)

---

## Stage 3: Dirichlet Attribution Weighting

When content has multiple contributors (agents, humans, services), Dirichlet distributions ensure **fair, non-zero attribution**.

### Mathematical Foundation

The Dirichlet distribution Dir(alpha) is the conjugate prior for the multinomial distribution:

```
weights ~ Dir(alpha_1, alpha_2, ..., alpha_K)

Expected weight for contributor i:
  E[w_i] = alpha_i / sum(alpha)

Concentration parameter:
  sum(alpha) controls spread:
    - Low sum(alpha) → spiky (one contributor dominates)
    - High sum(alpha) → uniform (equal attribution)
```

### Fairness Guarantee

With `alpha_i >= 1` for all contributors, **no contributor receives zero weight**. This is the core fairness property — even minimal contributions get non-zero attribution.

### Configuration

```typescript
interface DirichletConfig {
  smoothingAlpha: number;    // 0.1 = spiky, 10 = uniform (default: 0.1)
  concentrationK: number;    // Overall concentration (default: 1.0)
  decayHalfLife: number;     // Weeks before contribution halves (default: 12)
}
```

### Attribution Flow

```
Raw Contributions → Alpha Assignment → Decay Application → Normalization → Weights
      $50              alpha = 51        * exp(-rate*t)      / sum(alpha)    0.32
```

1. **Alpha Assignment**: `alpha_i = smoothingAlpha + (amount * concentrationK)`
2. **Temporal Decay**: `alpha_new = alpha_old * exp(-ln(2) / halfLife * weeks_inactive)`
3. **Normalization**: `weight_i = alpha_i / sum(all_alpha)`
4. **Merkle Proof**: Each weight gets a leaf hash for verification

### Output Structure

```typescript
interface ContributionWeight {
  address: string;          // Contributor identifier
  weight: number;           // [0, 1], all weights sum to 1
  rawContribution: number;  // Pre-weighting amount
  alphaComponent: number;   // Individual alpha value
  category: string;         // Contract type (groceries, grotoken, etc.)
}
```

### Why Dirichlet?

- **Closed-form Bayesian update**: New data updates alpha directly (no recomputation)
- **Conjugate prior**: Mathematically elegant for categorical/multinomial data
- **Fairness by construction**: Non-zero guarantee with alpha >= 1
- **Interpretable**: Each alpha_i is "pseudo-count" of contributions

---

## Stage 4: Hyperbolic Geometry Encoding

Content hierarchies are encoded in the **Poincare disk model** — a 2D representation of hyperbolic space with curvature K = -1.

### Why Hyperbolic Space?

| Property | Euclidean (flat) | Hyperbolic (curved) |
|----------|-----------------|-------------------|
| **Area growth** | ~r^2 (polynomial) | ~e^r (exponential) |
| **Tree embedding** | O(sqrt(n)) distortion | O(log n) distortion |
| **Hierarchy encoding** | Poor (flat structure) | Natural (center = root) |
| **Volume at radius r** | Pi * r^2 | 2*Pi*(cosh(r) - 1) |

Hyperbolic space is **exponentially more capacious** than Euclidean space. A tree with n nodes can be embedded with only O(log n) distortion, compared to O(sqrt(n)) in Euclidean space. This makes it ideal for encoding hierarchical content structures.

### Poincare Disk Model

The Poincare disk is the open unit disk {(x,y) : x^2 + y^2 < 1} with the metric:

```
ds^2 = 4 * (dx^2 + dy^2) / (1 - x^2 - y^2)^2
```

Key properties:
- **Origin** (0, 0) = root/aggregate concept
- **Boundary** (unit circle) = infinity in hyperbolic space
- **Distance** grows logarithmically toward the boundary
- **Geodesics** are circular arcs orthogonal to the boundary

### Distance Formula

```
d_hyp(u, v) = arcosh(1 + 2 * ||u - v||^2 / ((1 - ||u||^2) * (1 - ||v||^2)))
```

Near the boundary (||u|| -> 1), small Euclidean differences map to large hyperbolic distances. This is what gives the disk its exponential capacity.

### Mobius Addition (Hyperbolic Translation)

```
u (+) v = ((1 + 2<u,v> + ||v||^2) * u + (1 - ||u||^2) * v)
          / (1 + 2<u,v> + ||u||^2 * ||v||^2)
```

Note: Mobius addition is **non-commutative** (u (+) v != v (+) u). This reflects the curvature of the space.

### Encoding Hierarchy

```
Layer 0 (origin, r ~ 0):     Aggregate concepts (economy total, document summary)
Layer 1 (r ~ 0.3):           Contract types / Super-nodes (GroToken, FoodUSD)
Layer 2 (r ~ 0.5-0.7):       Constellations (topic clusters)
Layer 3 (r ~ 0.8-0.95):      Individual points (transactions, sentences)
```

### Configuration

```typescript
interface EncoderConfig {
  curvature: number;       // -1 (fixed for Poincare disk)
  baseRadius: number;      // 0.3 (first-level node placement)
  radiusGrowth: number;    // 1.3 (growth per level)
  angularSpread: number;   // Angular distribution for siblings
  maxRadius: number;       // 0.95 (must be < 1.0 for numerical stability)
}
```

### Output: Poincare Points

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

### CGP Integration

Each super-node gets a `hyperbolic` field:

```json
{
  "hyperbolic": {
    "poincare": [0.1, -0.05],
    "curvature": -1.0
  }
}
```

---

## Stage 5: Zeta Spectral Filtering

Zeta filtering enhances meaningful spectral patterns using the **non-trivial zeros of the Riemann zeta function** as resonant frequencies.

### Mathematical Basis

The Riemann zeta function zeta(s) = sum(1/n^s, n=1..inf) has non-trivial zeros at s = 1/2 + i*gamma_k:

| k | gamma_k (imaginary part) |
|---|-------------------------|
| 1 | 14.134725... |
| 2 | 21.022039... |
| 3 | 25.010857... |
| 4 | 30.424876... |
| 5 | 32.935061... |
| ... | ... |
| 10 | 49.773832... |
| 20 | 77.144840... |

These zeros encode the **intrinsic frequencies of prime number distribution** — fundamental harmonic patterns in number theory.

### Why Zeta Zeros?

The connection between zeta zeros and information: prime numbers are the "atoms" of multiplicative number theory. Their distribution exhibits quasi-random patterns that zeta zeros characterize. By filtering signals through these frequencies, we:

1. **Enhance patterns** that align with fundamental mathematical harmonics
2. **Suppress noise** that doesn't resonate with prime structure
3. **Achieve scale invariance** — zeta zeros work across all data granularities

### Filter Mechanism

```python
# For each spectrum bin at frequency f:
weight[k] = exp(-(f - gamma[k])^2 / (2 * sigma^2))  # Gaussian kernel

# Weighted combination:
filtered_value = sum(weight[k] * input_spectrum[f] for k in 1..numZeros)
```

### Configuration

```typescript
interface ZetaFilterConfig {
  numZeros: number;          // 1-20 zeros to use (default: 10)
  decayFactor: number;       // 0-1, higher zeros decay (default: 0.9)
  normalizeOutput: boolean;  // Normalize result to [0,1] (default: true)
}
```

### Output: Spectral Analysis

```typescript
interface SpectralAnalysis {
  filtered: number[];      // Zeta-weighted spectrum values
  dominantIndex: number;   // Peak frequency index
  concentration: number;   // Gini-like energy measure [0,1]
  entropy: number;         // Shannon entropy of filtered spectrum
}
```

### In the CGP

Each constellation carries both raw and zeta-filtered spectra:

```json
{
  "spectrum": [0.08, 0.11, 0.15, 0.22, 0.18, 0.12, 0.08, 0.06],
  "spectrum_zeta": [0.09, 0.12, 0.16, 0.23, 0.17, 0.11, 0.07, 0.05]
}
```

The `spectrum_zeta` field is optional but recommended — it provides enhanced signal-to-noise for downstream consumers.

---

## Stage 6: CGP Packet Construction

All preceding stages converge into a single JSON document: the **CHIT Geometry Packet (CGP) v1.0**.

### Complete Structure

```json
{
  "spec": "chit.cgp.v1.0",

  "meta": {
    "source": "text",
    "units_mode": "sentences",
    "K": 8,
    "bins": 8,
    "backend": "sentence-transformers/all-MiniLM-L6-v2",
    "mhep": 72.3,
    "Hg_traj": [0.98, 0.92, 0.85, 0.77],
    "Hs_traj": [1.22, 1.15, 1.08, 1.01],
    "created_at": "2026-03-11T12:00:00Z",
    "encoder_version": "1.0.0",
    "zeta_filtering": true
  },

  "sig": { ... },

  "super_nodes": [
    {
      "id": "super_0",
      "label": "Resonant Mode 0",
      "summary": "Semantic cluster description",
      "x": -212.3,
      "y": 148.1,
      "r": 260.0,
      "hyperbolic": {
        "poincare": [0.1, -0.05],
        "curvature": -1.0
      },
      "constellations": [
        {
          "id": "const_0_0",
          "label": "Constellation Label",
          "summary": "Topic keywords",
          "anchor": [0.012, -0.31, 0.82, "...", 0.15],
          "radial_minmax": [-0.45, 0.93],
          "spectrum": [0.08, 0.11, 0.15, 0.22, 0.18, 0.12, 0.08, 0.06],
          "spectrum_zeta": [0.09, 0.12, 0.16, 0.23, 0.17, 0.11, 0.07, 0.05],
          "points": [
            {
              "id": "pt_0_0_0",
              "x": 13.4,
              "y": -8.2,
              "proj": 0.83,
              "conf": 0.94,
              "text": "Original unit text...",
              "text_b64": "SGVsbG8gd29ybGQ=",
              "char_len": 127,
              "word_count": 22,
              "contributor_id": "agent-zero",
              "merkle_proof": ["hash1", "hash2"],
              "weight": 0.85
            }
          ],
          "maca_consensus": {
            "entropy_delta": 0.34,
            "votes": [3, 4, 2],
            "confidence": 0.85
          }
        }
      ]
    }
  ]
}
```

### Field Requirements

| Field | Required | Validation Rule |
|-------|----------|----------------|
| `spec` | Yes | Must be `"chit.cgp.v1.0"` |
| `meta.source` | Yes | One of: docx, text, latent, image, audio, video |
| `meta.units_mode` | Yes | One of: paragraphs, sentences, tokens, frames, samples |
| `meta.K` | Yes | Integer 4-16 |
| `meta.bins` | Yes | Integer 5-12 |
| `anchor` | Yes | Float array, L2 norm = 1.0 |
| `radial_minmax` | Yes | [min, max] projection bounds |
| `spectrum` | Yes | Float array, sums to 1.0 |
| `points[].proj` | Recommended | Within radial_minmax bounds |
| `points[].conf` | Recommended | Float [0, 1] |
| `sig.hmac` | Optional | Base64-encoded HMAC-SHA256 |

### Construction Code

```python
from pmoves.tools.chit import build_cgp

cgp = build_cgp(
    anchors=U,             # (K, D) anchor matrix from CHR
    spectra=spectra,       # (K, bins) from CHR
    embeddings=embeddings, # (N, D) original embeddings
    texts=texts,           # N original text units
    meta={
        "source": "text",
        "units_mode": "sentences",
        "K": 8,
        "bins": 8,
        "backend": "sentence-transformers/all-MiniLM-L6-v2"
    }
)
```

See [CGP_ENCODING_REFERENCE.md](CGP_ENCODING_REFERENCE.md) for field-by-field construction details.

---

## Stage 7: Security (Signing & Encryption)

### HMAC Signing

CGP packets are signed with HMAC-SHA256 for integrity and authenticity:

```python
from pmoves.tools.chit_security import sign_cgp

# Sign the packet
cgp_signed = sign_cgp(cgp, passphrase="shared-secret")

# Verification
from pmoves.tools.chit_security import verify_cgp
is_valid = verify_cgp(cgp_signed, passphrase="shared-secret")
```

**Signing process:**

1. Deep-copy the payload
2. Remove any existing `sig` block
3. Canonicalize: `json.dumps(payload, sort_keys=True, separators=(",", ":"))`
4. Compute: `HMAC-SHA256(canonical_json, passphrase)`
5. Attach `sig` block with `alg`, `kid` (first 16 chars of SHA256(passphrase)), and base64 `hmac`

### Anchor Encryption

For confidential content, anchor vectors can be encrypted with AES-GCM:

```python
from pmoves.tools.chit_security import encrypt_anchors

cgp_protected = encrypt_anchors(cgp_signed, passphrase="shared-secret")
# Each constellation's `anchor` field is replaced with `anchor_enc`:
# {
#   "alg": "AES-GCM",
#   "iv": "base64-iv",
#   "salt": "base64-salt",
#   "ct": "base64-ciphertext"
# }
```

With encrypted anchors, the CGP's geometric structure (spectra, positions) remains visible for routing and filtering, but the actual semantic content (anchor directions) is protected.

---

## Stage 8: Transport (GEOMETRY BUS)

CGP packets travel over the NATS-based GEOMETRY BUS.

### Primary NATS Subjects

| Subject | Publisher | Subscriber | Payload |
|---------|-----------|-----------|---------|
| `tokenism.cgp.ready.v1` | DeepResearch, SupaSerch, ToKenism | Hi-RAG v2, shape-store | Full CGP packet |
| `geometry.cgp.v1` | Hi-RAG v2, Gateway | Consumers | CGP transport |
| `geometry.event.v1` | Any | Persistence layer | Raw geometry persistence |
| `tokenism.attribution.recorded.v1` | ToKenism | Audit trail | Per-action attribution |
| `tokenism.cgp.weekly.v1` | ToKenism | Analytics | Weekly CGP export |
| `geometry.swarm.meta.v1` | EvoSwarm | Parameter consumers | Swarm optimization state |
| `tokenism.swarm.population.v1` | ToKenism | EvoSwarm | Attribution fairness metrics |

### Publishing

```python
import nats
import json

async def publish_cgp(cgp):
    nc = nats.NATS()
    await nc.connect("nats://nats:pmoves@nats:4222")
    await nc.publish(
        "tokenism.cgp.ready.v1",
        json.dumps(cgp).encode()
    )
    await nc.close()
```

### JetStream Persistence

CGP packets published to JetStream-backed subjects are durably stored:

```bash
# Create stream for CGP persistence
nats stream add GEOMETRY_CGPS \
  --subjects "geometry.cgp.v1,tokenism.cgp.ready.v1" \
  --storage file \
  --retention limits \
  --max-msgs 100000
```

---

## Stage 9: Decoding & Reconstruction

### Three Decoding Modes

#### Mode 1: Exact (Lossless)

When `points[].text` or `points[].text_b64` is present, content is recovered directly:

```python
decoded_text = base64.b64decode(point["text_b64"]).decode("utf-8")
# or simply: decoded_text = point["text"]
```

#### Mode 2: Geometry-Only (Lossy/Retrieval)

When only geometric information is available (anchor, spectrum, radial_minmax), content is **reconstructed** from a shared corpus:

```
For each constellation:
  1. Project all corpus embeddings onto the anchor vector
  2. Bin projections into the same histogram structure as the spectrum
  3. Select corpus items whose projection distribution matches the target spectrum
  4. Rank by KL divergence between empirical and target distributions
```

This is the **Universal Codebook Property**: when encoder and decoder share the same embedding model and corpus, meaning can be reconstructed purely from geometry without transmitting raw tokens.

#### Mode 3: Multi-Modal

For image/audio/video CGPs, use the appropriate embedding model:

```python
from pmoves.tools.chit import decode_images

results = decode_images(
    "cgp_clip.json",
    image_dir="./images",
    model_name="clip-ViT-B-32"
)
```

### Calibration Metrics

After decoding, measure reconstruction quality:

```python
from pmoves.tools.chit.chit_decoder import compute_metrics

metrics = compute_metrics(
    cgp=cgp,
    decoded=results,
    corpus_texts=texts,
    corpus_vecs=vecs
)
```

| Metric | Good | Description |
|--------|------|-------------|
| KL Divergence | < 0.5 | Spectrum distribution match |
| JS Divergence | < 0.3 | Symmetric distribution distance |
| Wasserstein-1D | < 0.2 | Earth-mover distance |
| Coverage | > 0.8 | Fraction of content recovered |

See [CALIBRATION_GUIDE.md](CALIBRATION_GUIDE.md) for detailed calibration procedures.

---

## Stage 10: Swarm Optimization Feedback

The pipeline is not one-shot — EvoSwarm continuously optimizes the encoding parameters.

### Feedback Loop

```
CGP Telemetry → EvoSwarm Controller → Parameter Evolution → Updated Config
     ↑                                                           ↓
     └─────── New CGPs with better parameters ←──────────────────┘
```

### What Gets Optimized

| Parameter | Genome Field | Effect |
|-----------|-------------|--------|
| K (constellations) | `cg_builder.K` | Cluster granularity |
| bins (spectrum) | `cg_builder.bins` | Spectral resolution |
| tau (temperature) | `cg_builder.tau` | Assignment hardness |
| beta (regularization) | `cg_builder.beta` | Anchor stability |
| Decoder mode | `decoder.mode` | Reconstruction strategy |
| HRM threshold | `decoder.hrm_halt_thresh` | Refinement stopping |

### Fitness Evaluation

```
fitness = weighted_sum(
  reconstruction_quality,  // KL divergence of decoded output
  compression_ratio,       // CGP size vs original content size
  attribution_fairness,    // Gini coefficient of weights
  energy_efficiency         // GPU watts * decode time
)
```

### Parameter Pack Distribution

Optimized parameters are published as **parameter packs** via NATS:

```json
{
  "pack_id": "pack-12345",
  "namespace": "default",
  "status": "active",
  "best_fitness": 0.94,
  "parameters": {
    "cg_builder": { "K": 8, "bins": 8, "tau": 0.1, "beta": 0.01 },
    "decoder": { "mode": "swarm", "hrm_halt_thresh": 0.95 }
  }
}
```

Published on `geometry.swarm.meta.v1` for all encoding services to consume.

---

## Complete Data Flow Diagram

```
                              PMOVES.AI CHIT Mathematical Pipeline
                              ======================================

    ┌─────────┐     ┌───────────┐     ┌─────────┐     ┌───────────┐
    │  Text   │     │  Image    │     │  Audio  │     │  Video    │
    │ Content │     │ Content   │     │ Content │     │ Content   │
    └────┬────┘     └─────┬─────┘     └────┬────┘     └─────┬─────┘
         │                │                 │                 │
         ▼                ▼                 ▼                 ▼
    ┌──────────────────────────────────────────────────────────────┐
    │                 STAGE 1: EMBEDDING                           │
    │  MiniLM-L6-v2 (text)  |  CLIP ViT-B-32 (image)  | Whisper  │
    │  Output: (N, D) normalized vectors                          │
    └──────────────────────────┬───────────────────────────────────┘
                               │
                               ▼
    ┌──────────────────────────────────────────────────────────────┐
    │          STAGE 2: CONSTELLATION HARVEST (CHR)                │
    │                                                              │
    │  Alternating Minimization:                                   │
    │    E-step: assignments p[i][k] via softmax                   │
    │    M-step: anchors U[k] via weighted mean + normalize        │
    │                                                              │
    │  Output: K anchors, N×K assignments, K×bins spectra          │
    └──────────────────────────┬───────────────────────────────────┘
                               │
                    ┌──────────┼──────────┐
                    ▼          ▼          ▼
         ┌──────────────┐ ┌────────┐ ┌──────────────┐
         │   STAGE 3    │ │STAGE 4 │ │   STAGE 5    │
         │  Dirichlet   │ │Poincare│ │ Zeta Filter  │
         │  Weights     │ │ Disk   │ │  (gamma_k)   │
         │              │ │        │ │              │
         │ alpha → w_i  │ │(x,y,r) │ │ spectrum →   │
         │ + Merkle     │ │encoding│ │ spectrum_zeta│
         └──────┬───────┘ └───┬────┘ └──────┬───────┘
                │             │              │
                └─────────────┼──────────────┘
                              │
                              ▼
    ┌──────────────────────────────────────────────────────────────┐
    │               STAGE 6: CGP PACKET CONSTRUCTION               │
    │                                                              │
    │  { spec: "chit.cgp.v1.0", meta: {...},                      │
    │    super_nodes: [{ constellations: [{                        │
    │      anchor, spectrum, spectrum_zeta, points: [{             │
    │        proj, conf, weight, merkle_proof, text               │
    │      }] }] }] }                                             │
    └──────────────────────────┬───────────────────────────────────┘
                               │
                               ▼
    ┌──────────────────────────────────────────────────────────────┐
    │               STAGE 7: SECURITY                              │
    │  sign_cgp() → HMAC-SHA256 sig block                         │
    │  encrypt_anchors() → AES-GCM anchor_enc (optional)          │
    └──────────────────────────┬───────────────────────────────────┘
                               │
                               ▼
    ┌──────────────────────────────────────────────────────────────┐
    │               STAGE 8: GEOMETRY BUS (NATS)                   │
    │  tokenism.cgp.ready.v1  |  geometry.cgp.v1                  │
    │  JetStream-persisted for durable delivery                   │
    └────────────┬─────────────────────────────┬──────────────────┘
                 │                             │
                 ▼                             ▼
    ┌────────────────────┐        ┌────────────────────────┐
    │ STAGE 9: DECODE    │        │ STAGE 10: EVOSWARM     │
    │                    │        │ FEEDBACK LOOP           │
    │ Exact / Geometry / │        │                        │
    │ Multi-modal        │        │ Fitness evaluation →   │
    │                    │        │ Parameter evolution →  │
    │ KL < 0.5 target    │        │ Updated parameter pack │
    └────────────────────┘        └────────────────────────┘
```

---

## Cross-References

### Protocol Specifications
- [CGP v1.0 Specification](CGP_v1.0_SPECIFICATION.md) — Wire format definition
- [CGP Encoding Reference](CGP_ENCODING_REFERENCE.md) — Field-by-field construction guide
- [Calibration Guide](CALIBRATION_GUIDE.md) — KL/JS divergence calibration procedures

### Mathematical Foundations
- [Integrating Math into PMOVES.AI](Integrating%20Math%20into%20PMOVES.AI.md) — Conceptual pillars
- [Three-Body Doctrine](THREE_BODY_DOCTRINE.md) — Philosophical framework
- [Constellation-Harvest-Regularization](Constellation-Harvest-Regularization/) — CHR deep dive

### Implementation
- [TypeScript Modules](../../PMOVES-ToKenism-Multi/integrations/contracts/chit/) — 7 TS modules
- [CHIT Tools Catalog](../CHIT_TOOLS_CATALOG.md) — Python tooling reference
- [Mathematical UI Specification](Mathematical_UI_Design_Specification.md) — Visualization spec

### Transport & Operations
- [GEOMETRY BUS Integration](GEOMETRY_BUS_INTEGRATION.md) — NATS integration guide
- [GEOMETRY NATS Subjects](../../.claude/context/geometry-nats-subjects.md) — Subject catalog
- [EvoSwarm Operations](../EVOSWARM_OPERATIONS_GUIDE.md) — Parameter optimization ops

### Security
- [CHIT User Guide](CHIT_USER_GUIDE.md) — End-user signing/encryption guide
- [Security Patterns](../../.claude/context/security-patterns.md) — Cross-cutting security

---

*This document is a living artifact tracked by [CHIT_CHANGE_TRACKER.md](../CHIT_CHANGE_TRACKER.md).*
