> **Canonical Specification** — This is the authoritative CGP protocol reference.
> Start here: [README.md](README.md) · API usage: [API Reference](04_API_REFERENCE.md)

# CHIT Geometry Packet (CGP) v1.0 Specification

**Comprehensive specification for the CHIT (Cymatic-Holographic Information Transfer) protocol**

**Version:** 1.0
**Status:** Production Ready
**Date:** February 8, 2026
**Authors:** PMOVES.AI Team

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Mathematical Foundations](#mathematical-foundations)
3. [CGP Schema v1.0](#cgp-schema-v10)
4. [Encoding Pipeline](#encoding-pipeline)
5. [Decoding Pipeline](#decoding-pipeline)
6. [Security Layer](#security-layer)
7. [NATS Integration (GEOMETRY_BUS)](#nats-integration-geometry_bus)
8. [Multi-Modal Extensions](#multi-modal-extensions)
9. [Implementation Reference](#implementation-reference)
10. [Migration Guide](#migration-guide)

---

## Executive Summary

CHIT (Cymatic-Holographic Information Transfer) is a **geometric protocol for information encoding** that transforms data into boundary representations (CGP packets) enabling:

- **Holographic Compression**: Information encoded on "surfaces" rather than volumes
- **Universal Translatability**: Geometry-only mode enables shared codebook communication
- **Provenance Tracking**: Merkle-proof attribution chains
- **Spectral Signal Processing**: Zeta-inspired filtering for noise reduction
- **Hyperbolic Hierarchy**: Exponential storage capacity via Poincaré disk encoding

**Key Innovation:** By encoding information as geometric constellations (anchor directions + radial spectra), CHIT enables "telepathy-like" communication where receivers reconstruct meaning purely from shape, without transmitting raw tokens.

---

## Mathematical Foundations

### The Five Mathematical Pillars

| Pillar | Mathematical Basis | Implementation | Purpose |
|--------|-------------------|----------------|---------|
| **1. Dirichlet Distributions** | Bayesian conjugate priors for multinomial | `DirichletWeights.ts` | Fair attribution weight distribution |
| **2. Hyperbolic Geometry** | Poincaré disk model (curvature = -1) | `HyperbolicEncoder.ts` | Hierarchical embedding with exponential capacity |
| **3. Merkle Proofs** | Hash-based verification trees | `ShapeAttribution.ts` | Tamper-proof attribution chains |
| **4. Zeta Spectral Filtering** | Riemann zeta zeros (γₖ) as filter weights | `ZetaFilter.ts` | Signal enhancement via prime frequency resonance |
| **5. Swarm Optimization** | Evolutionary algorithms (EvoSwarm) | `SwarmAttribution.ts` | Distributed consensus without backpropagation |

### 1. Dirichlet Distributions

**Purpose:** Probabilistic attribution weighting with built-in fairness

The Dirichlet distribution Dir(α₁, ..., αₖ) is the conjugate prior for multinomial distributions. For CHIT attribution:

```
weights = Dir(α = [α₁, α₂, ..., αₖ])
where αᵢ = 1 + prior_countᵢ (minimum 1 for uniform prior)
```

**Properties:**
- **Concentration parameter:** Σαᵢ controls spread (higher = more concentrated)
- **Fairness guarantee:** With αᵢ ≥ 1, all contributors receive non-zero weight
- **Update rule:** Posterior α' = α + counts (closed-form Bayesian update)

**Implementation Reference:** `PMOVES-ToKenism-Multi/integrations/contracts/chit/dirichlet-weights.ts`

### 2. Hyperbolic Geometry (Poincaré Disk)

**Purpose:** Exponential storage capacity for hierarchical data

The Poincaré disk model represents hyperbolic space (curvature K = -1) as the unit disk:

```
Distance metric:
d_hyp(x, y) = arcosh(1 + 2 * ||x - y||² / ((1 - ||x||²) * (1 - ||y||²)))

Möbius addition (non-commutative):
x ⊕ y = ((1 + 2⟨x,y⟩ + ||y||²)x + (1 - ||x||²)y) / (1 + 2⟨x,y⟩ + ||x||²||y||²)
```

**Properties:**
- **Exponential volume:** Area grows as ~e^r (vs ~r² in Euclidean)
- **Natural hierarchy:** Root concepts at origin, leaves at boundary
- **Tree embedding:** O(log n) distortion for n-node trees

**Implementation Reference:** `PMOVES-ToKenism-Multi/integrations/contracts/chit/hyperbolic-encoder.ts`

### 3. Merkle Proofs

**Purpose:** Tamper-proof attribution chains

Each constellation includes a Merkle root proving contribution integrity:

```
leaf_hash = H(contributor_id || contribution_hash || weight)
merkle_root = build_tree([leaf_hash₁, leaf_hash₂, ...])
proof = merkle_proof(leaf_hashᵢ, merkle_root)
```

**Verification:**
```python
verify(proof, leaf, root) := compute_root_from_proof(proof) == root
```

**Implementation Reference:** `PMOVES-ToKenism-Multi/integrations/contracts/chit/shape-attribution.ts`

### 4. Zeta Spectral Filtering

**Purpose:** Signal enhancement using Riemann zeta zero frequencies

The Riemann zeta function ζ(s) has non-trivial zeros at s = 1/2 + iγₖ:
- γ₁ ≈ 14.1347
- γ₂ ≈ 21.0220
- γ₃ ≈ 25.0109
- ...

These zeros represent intrinsic frequencies of prime number distribution.

**Filter weights:**
```python
wₖ = exp(-(f - γₖ)² / (2σ²))  # Gaussian kernel around each zero
filtered_spectrum = Σₖ wₖ * input_spectrum
```

**Properties:**
- **Signal enhancement:** Meaningful patterns often align with zeta resonances
- **Noise reduction:** Non-harmonic noise filtered automatically
- **Scale invariance:** Works across data granularities

**Implementation Reference:** `PMOVES-ToKenism-Multi/integrations/contracts/chit/zeta-filter.ts` and `pmoves/tools/zeta_filter.py`

### 5. Swarm Optimization (EvoSwarm)

**Purpose:** Distributed consensus without gradient descent

Evolutionary algorithm optimizing attribution via:
1. **Mutation:** Perturb weights with Dirichlet noise
2. **Crossover:** Recombine weight vectors between agents
3. **Selection:** Keep top-K by fitness (entropy reduction)

**Fitness function:**
```
fitness = -H_posterior + λ * fairness_penalty
where H_posterior = entropy after applying weights
```

**Implementation Reference:** `PMOVES-ToKenism-Multi/integrations/contracts/chit/swarm-attribution.ts`

---

## CGP Schema v1.0

### Complete Schema

```json
{
  "spec": "chit.cgp.v1.0",

  // === Metadata ===
  "meta": {
    // Required fields
    "source": "docx|text|latent|image|audio|video",
    "units_mode": "paragraphs|sentences|tokens|frames|samples",
    "K": 8,                    // Number of constellations
    "bins": 8,                 // Spectrum resolution
    "backend": "sentence-transformers/all-MiniLM-L6-v2",

    // Optional quality metrics
    "mhep": 72.3,              // Multi-scale Hyperbolic Entropy Product
    "Hg_traj": [0.98, 0.77],   // Global entropy trajectory
    "Hs_traj": [1.22, 1.01],   // Slab entropy trajectory

    // Processing info
    "created_at": "2026-02-08T12:00:00Z",
    "encoder_version": "1.0.0",
    "zeta_filtering": true
  },

  // === Security (Optional) ===
  "sig": {
    "alg": "HMAC-SHA256",
    "kid": "key-identifier-16chars",
    "ts": 1739001600,
    "hmac": "base64-encoded-hmac"
  },

  // === Geometric Data ===
  "super_nodes": [
    {
      "id": "super_0",
      "label": "Resonant Mode 0",
      "summary": "Semantic cluster description",

      // 2D layout for visualization (PCA or UMAP)
      "x": -212.3,
      "y": 148.1,
      "r": 260.0,

      // Hyperbolic encoding (optional)
      "hyperbolic": {
        "poincare": [0.1, -0.05],  // Poincaré disk coordinates
        "curvature": -1.0
      },

      "constellations": [
        {
          "id": "const_0_0",
          "label": "Constellation Label",
          "summary": "Topic keywords or semantic summary",

          // === Core Geometric Fields ===

          // Anchor direction (unit vector in embedding space)
          "anchor": [0.012, -0.31, 0.82, ..., 0.15],

          // Radial bounds along anchor
          "radial_minmax": [-0.45, 0.93],

          // Energy spectrum (histogram over radial bins)
          "spectrum": [0.08, 0.11, 0.15, 0.20, 0.18, 0.12, 0.10, 0.06],

          // Zeta-filtered spectrum (optional)
          "spectrum_zeta": [0.09, 0.12, 0.16, 0.19, 0.17, 0.11, 0.09, 0.07],

          // === Content Points (Optional for Geometry-Only Mode) ===
          "points": [
            {
              "id": "pt_0_0_0",

              // 2D visualization coordinates
              "x": 13.4,
              "y": -8.2,

              // Projection onto anchor
              "proj": 0.83,
              "conf": 0.94,  // Max p_ij (assignment confidence)

              // Content (can be omitted for geometry-only)
              "text": "Original unit text...",
              "text_b64": "SGVsbG8gd29ybGQ=",  // Base64 encoded

              // Metadata
              "char_len": 127,
              "word_count": 22,
              "embedding": [0.1, 0.2, ...],  // Optional: raw embedding

              // Attribution (Merkle proof)
              "contributor_id": "agent-zero",
              "merkle_proof": ["hash1", "hash2"],
              "weight": 0.85
            }
          ],

          // === MACA Consensus (Optional) ===
          "maca_consensus": {
            "entropy_delta": 0.34,
            "votes": [3, 4, 2],
            "confidence": 0.85
          },

          // === Security (Optional) ===
          "anchor_enc": {  // Encrypted anchor (AES-GCM)
            "alg": "AES-GCM",
            "iv": "base64-iv",
            "salt": "base64-salt",
            "ct": "base64-ciphertext"
          }
        }
      ]
    }
  ],

  // === NATS Integration (Optional) ===
  "nats": {
    "subject": "tokenism.geometry.event.v1",
    "timestamp": "2026-02-08T12:00:00Z",
    "publisher_id": "chit-publisher-01",
    "stream": "GEOMETRY_CGP"
  }
}
```

### Field Specifications

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `spec` | string | ✅ | Protocol version: `"chit.cgp.v1.0"` |
| `meta.source` | enum | ✅ | Content type: `docx|text|latent|image|audio|video` |
| `meta.units_mode` | enum | ✅ | Granularity: `paragraphs|sentences|tokens|frames|samples` |
| `meta.K` | int | ✅ | Number of constellations (typically 4-16) |
| `meta.bins` | int | ✅ | Spectrum resolution (typically 5-12) |
| `meta.backend` | string | ✅ | Embedding model used |
| `meta.mhep` | float | ⏸ | Multi-scale Hyperbolic Entropy Product |
| `meta.Hg_traj` | float[] | ⏸ | Global entropy trajectory |
| `meta.Hs_traj` | float[] | ⏸ | Slab entropy trajectory |
| `sig` | object | ⏸ | HMAC-SHA256 signature |
| `super_nodes[].id` | string | ✅ | Unique super node identifier |
| `super_nodes[].label` | string | ⏸ | Human-readable label |
| `super_nodes[].x` | float | ⏸ | 2D layout coordinate (PCA) |
| `super_nodes[].y` | float | ⏸ | 2D layout coordinate (PCA) |
| `super_nodes[].hyperbolic` | object | ⏸ | Poincaré disk encoding |
| `constellations[].id` | string | ✅ | Unique constellation identifier |
| `constellations[].anchor` | float[] | ✅ | Unit vector direction (dim = embedding) |
| `constellations[].radial_minmax` | [float, float] | ✅ | [min, max] projection bounds |
| `constellations[].spectrum` | float[] | ✅ | Energy distribution (length = bins) |
| `constellations[].spectrum_zeta` | float[] | ⏸ | Zeta-filtered spectrum |
| `constellations[].points` | array | ⏸ | Content points (omit for geometry-only) |
| `constellations[].maca_consensus` | object | ⏸ | MACA voting results |
| `constellations[].anchor_enc` | object | ⏸ | Encrypted anchor (AES-GCM) |
| `nats` | object | ⏸ | NATS publishing metadata |

### Version History

| Version | Date | Changes |
|---------|------|---------|
| v0.1 | 2025-12 | Initial specification |
| v0.2 | 2025-12 | Added NATS integration, zeta filtering |
| **v1.0** | 2026-02-08 | **Production-ready: MACA consensus, security, multi-modal** |

---

## Encoding Pipeline

### Overview

```
Input Content → Embedding → CHR Analysis → CGP Generation → NATS Publish
     ↓              ↓             ↓             ↓              ↓
  Text/Image    Sentence     Constellation   CHIT Packet    GEOMETRY_BUS
                Transformers   Harvest        v1.0           Subjects
```

### Step 1: Content Embedding

```python
from sentence_transformers import SentenceTransformer

model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
embeddings = model.encode(texts, normalize_embeddings=True)
```

### Step 2: Constellation Harvest Regularization (CHR)

```python
from pmoves.tools.chr import ConstellationHarvest

chr = ConstellationHarvest(K=8, bins=8)

# Optimize anchor directions
U = chr.optimize_anchors(embeddings)  # Shape: (K, embedding_dim)

# Compute soft assignments
p = chr.compute_assignments(embeddings, U)  # Shape: (N, K)

# Compute spectra
spectra = chr.compute_spectra(embeddings, U, p, bins=8)

# Compute entropy trajectories
Hg_traj, Hs_traj = chr.compute_entropy_trajectory(embeddings, U, p)
```

### Step 3: Zeta Filtering (Optional)

```python
from pmoves.tools.zeta_filter import ZetaSpectralFilter

zeta = ZetaSpectralFilter(num_zeros=10)
filtered_spectra = [zeta.filter_spectrum(s) for s in spectra]
```

### Step 4: MACA Consensus (Optional)

```python
from pmoves.tools.maca_tensorzero import MACATensorZeroConsensus

maca = MACATensorZeroConsensus(tensorzero_url="http://localhost:3030")
consensus = await maca.multi_round_consensus(
    proposals=[{"spectrum": s, "anchor": a} for s, a in zip(spectra, U)],
    context={"task": "attribution"}
)
```

### Step 5: CGP Packet Construction

```python
from pmoves.tools.chit import build_cgp

cgp = build_cgp(
    anchors=U,
    spectra=spectra,
    embeddings=embeddings,
    texts=texts,
    meta={
        "source": "text",
        "units_mode": "sentences",
        "K": 8,
        "bins": 8,
        "backend": "sentence-transformers/all-MiniLM-L6-v2"
    }
)
```

### Step 6: Security (Optional)

```python
from pmoves.tools.chit_security import sign_cgp, encrypt_anchors

cgp_signed = sign_cgp(cgp, passphrase="shared-secret")
cgp_protected = encrypt_anchors(cgp_signed, passphrase="shared-secret")
```

### Step 7: NATS Publishing

```python
import asyncio
from nats.aio.client import Client as NATS

async def publish_cgp(cgp):
    nc = await NATS.connect()
    await nc.publish("tokenism.geometry.event.v1", json.dumps(cgp).encode())
    await nc.close()

asyncio.run(publish_cgp(cgp))
```

---

## Decoding Pipeline

### Overview

```
CGP Packet → Verify → Decrypt → Decode → Content
     ↓          ↓         ↓        ↓        ↓
  CHIT v1.0   HMAC    AES-GCM   Exact/   Text/
                      Geometry  Images/
                       Corpus    Audio
```

### Decoding Modes

#### 1. Exact Mode (Lossless)

Recovers content directly from embedded `points[].text`:

```python
from pmoves.tools.chit import decode_cgp

results = decode_cgp("cgp.json", mode="exact")
for r in results:
    print(f"{r['constellation_id']}: {r['text']}")
```

#### 2. Geometry-Only Mode (Lossy/Retrieval)

Reconstructs content by matching geometric constellations to a shared corpus:

```python
results = decode_cgp(
    "cgp.json",
    corpus_path="corpus.jsonl",
    mode="geometry",
    per_constellation=50
)
```

**How it works:**
1. Project all corpus embeddings onto each constellation's anchor
2. Match the empirical projection distribution to the target spectrum
3. Select items whose projections align with spectrum peaks

**Universal Codebook Property:** When encoder and decoder share the same embedding model and corpus, meaning can be reconstructed purely from geometry (anchor + spectrum) without transmitting raw tokens.

#### 3. Multi-Modal Decoding

```python
from pmoves.tools.chit import decode_images

# Decode to images using CLIP
results = decode_images(
    "cgp_clip.json",  # Must use CLIP backend
    image_dir="./images",
    model_name="clip-ViT-B-32"
)
```

### Calibration Metrics

Assess reconstruction fidelity:

```python
from pmoves.tools.chit.chit_decoder import compute_metrics

metrics = compute_metrics(
    cgp=cgp,
    decoded=results,
    corpus_texts=texts,
    corpus_vecs=vecs
)

print(f"KL Divergence: {metrics['mean']['KL']:.4f}")
print(f"JS Divergence: {metrics['mean']['JS']:.4f}")
print(f"Wasserstein-1D: {metrics['mean']['W1']:.4f}")
print(f"Coverage: {metrics['mean']['coverage']:.3f}")
```

---

## Security Layer

### HMAC-SHA256 Signing

```python
from pmoves.tools.chit_security import sign_cgp, verify_cgp

# Sign CGP
cgp_signed = sign_cgp(
    cgp,
    passphrase="shared-secret",
    kid="key-identifier"
)

# Verify signature
is_valid = verify_cgp(cgp_signed, "shared-secret")
```

**Signature format:**
```json
{
  "sig": {
    "alg": "HMAC-SHA256",
    "kid": "key-identifier-16chars",
    "ts": 1739001600,
    "hmac": "base64-encoded-hmac"
  }
}
```

### AES-GCM Anchor Encryption

```python
from pmoves.tools.chit_security import encrypt_anchors, decrypt_anchors

# Encrypt all constellation anchors
cgp_protected = encrypt_anchors(
    cgp,
    passphrase="shared-secret"
)

# Decrypt
cgp_decrypted = decrypt_anchors(
    cgp_protected,
    passphrase="shared-secret"
)
```

**Encryption format:**
```json
{
  "anchor_enc": {
    "alg": "AES-GCM",
    "iv": "base64-iv",
    "salt": "base64-salt",
    "ct": "base64-ciphertext"
  }
}
```

**Key derivation:** PBKDF2-HMAC-SHA256 with 600,000 iterations (OWASP 2024 recommendation)

---

## NATS Integration (GEOMETRY_BUS)

### Subject Hierarchy

```
tokenism.geometry.event.v1
├── geometry.packet.encoded.v1    (Hi-RAG publishes CGPs)
├── geometry.packet.decoded.v1    (Flute-Gateway subscribes)
├── geometry.attribution.request.v1  (Attribution queries)
├── geometry.attribution.result.v1  (Attribution responses)
└── geometry.visualization.request.v1  (Hyperdim viz requests)
```

### JetStream Streams

```bash
# Create persistent streams
nats stream create GEOMETRY_CGP \
  --subjects "tokenism.geometry.>" \
  --max-msgs-per-subject 10000 \
  --max-age 30d

nats stream create TOKENISM_ATTRIBUTION \
  --subjects "geometry.attribution.>" \
  --max-msgs-per-subject 5000 \
  --max-age 7d
```

### Publishing Example

```python
import asyncio
from nats.aio.client import Client as NATS

async def publish_geometry(cgp: dict):
    nc = await NATS.connect()

    # Publish to JetStream for persistence
    js = nc.jetstream()
    await js.publish(
        subject="tokenism.geometry.event.v1",
        payload=json.dumps(cgp).encode(),
        headers={
            "Nats-Expected-Stream": "GEOMETRY_CGP"
        }
    )

    await nc.close()
```

### Subscription Example

```python
async def subscribe_geometry():
    nc = await NATS.connect()
    js = nc.jetstream()

    async def on_message(msg):
        cgp = json.loads(msg.data)
        # Process CGP
        print(f"Received CGP: {cgp['meta']['source']}")

    await js.subscribe(
        subject="tokenism.geometry.event.v1",
        queue="geometry-workers",
        cb=on_message
    )
```

---

## Multi-Modal Extensions

### Image Encoding (CLIP)

```python
from sentence_transformers import SentenceTransformer

# Load CLIP model (text+image)
model = SentenceTransformer('clip-ViT-B-32')

# Encode images
image_embeddings = model.encode(
    [Image.open(p) for p in image_paths],
    convert_to_numpy=True,
    normalize_embeddings=True
)

# Encode text queries
text_embeddings = model.encode(
    ["a photo of a cat", "a photo of a dog"],
    convert_to_numpy=True,
    normalize_embeddings=True
)

# Compute similarity
similarity = image_embeddings @ text_embeddings.T
```

**CGP generation for images:**
- Set `meta.source = "image"`
- Set `meta.backend = "clip-ViT-B-32"`
- Points contain image metadata (path, dimensions, format)

### Audio Encoding (CLAP)

```python
import laion_clap

model = laion_clap.CLAP_Model(enable_fusion=True)
model.load_ckpt()

# Encode audio
audio_embeddings = model.encode_audio(
    audio_paths,
    embedding_mode="audio"
)

# Encode text
text_embeddings = model.encode_text(
    descriptions,
    embedding_mode="text"
)
```

### Cross-Modal Retrieval

The same CGP can retrieve content across modalities when using compatible embeddings:

```
Text CGP → Retrieve Images (CLIP text anchor → CLIP image embeddings)
Text CGP → Retrieve Audio (CLAP text anchor → CLAP audio embeddings)
Image CGP → Retrieve Text (CLIP image anchor → CLIP text embeddings)
```

---

## Implementation Reference

### TypeScript Modules

| Module | File | Purpose |
|--------|------|---------|
| `CGPGenerator` | `cgp-generator.ts` | Generate CGP v0.1/v0.2 packets |
| `DirichletWeights` | `dirichlet-weights.ts` | Dirichlet attribution |
| `HyperbolicEncoder` | `hyperbolic-encoder.ts` | Poincaré disk encoding |
| `ShapeAttribution` | `shape-attribution.ts` | Merkle proof attribution |
| `ZetaInspiredFilter` | `zeta-filter.ts` | Zeta spectral filtering |
| `SwarmAttribution` | `swarm-attribution.ts` | EvoSwarm consensus |
| `CHITNATSPublisher` | `chit-nats-publisher.ts` | NATS publishing |

**Location:** `PMOVES-ToKenism-Multi/integrations/contracts/chit/`

### Python Tools

| Tool | File | Purpose |
|------|------|---------|
| `chit_decoder.py` | `pmoves/tools/chit/chit_decoder.py` | Basic text decoder |
| `chit_decoder_mm.py` | `pmoves/tools/chit/chit_decoder_mm.py` | Multi-modal decoder |
| `chit_security.py` | `pmoves/tools/chit_security.py` | Security layer |
| `zeta_filter.py` | `pmoves/tools/zeta_filter.py` | Zeta spectral filtering |
| `maca_tensorzero.py` | `pmoves/tools/maca_tensorzero.py` | MACA consensus via TensorZero |

### CLI Commands

```bash
# Encoding (via TAC)
/chit:encode --input document.docx --output cgp.json --K 8

# Decoding
python -m pmoves.tools.chit.chit_decoder \
  --cgp cgp.json \
  --corpus corpus.jsonl \
  --mode geometry \
  --compute-metrics

# Multi-modal decoding
python -m pmoves.tools.chit.chit_decoder_mm \
  --cgp cgp_clip.json \
  --image-dir ./images

# Security
python -m pmoves.tools.chit_security \
  --sign cgp.json \
  --passphrase "shared-secret"
```

---

## Migration Guide

### From v0.2 to v1.0

**Breaking Changes:** None (v1.0 is backward compatible with v0.2)

**New Optional Fields:**
- `meta.zeta_filtering`: Boolean flag for zeta filtering
- `meta.encoder_version`: Encoder software version
- `constellations[].spectrum_zeta`: Zeta-filtered spectrum
- `constellations[].maca_consensus`: MACA voting results
- `constellations[].anchor_enc`: Encrypted anchor

**Recommended Updates:**
1. Add `meta.encoder_version` for debugging
2. Enable `meta.zeta_filtering` for noisy data
3. Use `maca_consensus` for multi-agent scenarios
4. Add `sig` field for production deployments

### Validation Checklist

Before deploying CGP v1.0 to production:

- [ ] All CGP packets include `spec: "chit.cgp.v1.0"`
- [ ] Anchor vectors are normalized (L2 norm = 1)
- [ ] Spectra sum to 1.0 (probability distribution)
- [ ] `points[].proj` values within `radial_minmax` bounds
- [ ] `sig.hmac` present for authenticated packets
- [ ] `anchor_enc` used instead of `anchor` for confidential data
- [ ] NATS JetStream streams created and validated
- [ ] Decoder calibration metrics within acceptable ranges (KL < 0.5, coverage > 0.8)

---

## Appendix

### A. Mathematical Definitions

**Hyperbolic Distance (Poincaré Disk):**
```
d_hyp(x, y) = arcosh(1 + 2 * ||x - y||² / ((1 - ||x||²)(1 - ||y||²)))
```

**Dirichlet Distribution:**
```
Dir(α₁, ..., αₖ) = (1/B(α)) * Πᵢ xᵢ^(αᵢ - 1)
where B(α) = Πᵢ Γ(αᵢ) / Γ(Σᵢ αᵢ)
```

**Zeta Function:**
```
ζ(s) = Σₙ n^(-s)
Zeros: ζ(1/2 + iγₖ) = 0
```

**KL Divergence:**
```
D_KL(P || Q) = Σₓ P(x) * log(P(x) / Q(x))
```

**Jensen-Shannon Divergence:**
```
D_JS(P || Q) = 0.5 * D_KL(P || M) + 0.5 * D_KL(Q || M)
where M = 0.5 * (P + Q)
```

### B. NATS Subject Reference

| Subject | Direction | Purpose |
|---------|-----------|---------|
| `tokenism.geometry.event.v1` | Pub | CHIT geometry events |
| `geometry.packet.encoded.v1` | Pub | Encoded CGP packets |
| `geometry.packet.decoded.v1` | Pub | Decoded content |
| `geometry.attribution.request.v1` | Pub | Attribution queries |
| `geometry.attribution.result.v1` | Pub | Attribution results |
| `geometry.visualization.request.v1` | Pub | Visualization requests |
| `geometry.visualization.ready.v1` | Pub | Visualization ready events |
| `evoswarm.population.v1` | Pub/Sub | Swarm optimization updates |

### C. Error Codes

| Code | Message | Resolution |
|------|---------|------------|
| `CGP_INVALID_SPEC` | Unknown CGP version | Use `"chit.cgp.v1.0"` |
| `CGP_MISSING_ANCHOR` | Constellation missing anchor | Add `anchor` array |
| `CGP_DIMENSION_MISMATCH` | Anchor dimension mismatch | Regenerate with matching backend |
| `CGP_INVALID_SPECTRUM` | Spectrum doesn't sum to 1 | Normalize spectrum |
| `CGP_SIGNATURE_INVALID` | HMAC verification failed | Check passphrase |
| `CGP_DECRYPTION_FAILED` | Anchor decryption failed | Check passphrase/salt |

### D. References

**Internal Documentation:**
- `PMOVESCHIT.md` - Core CHIT specification
- `GEOMETRY_BUS_INTEGRATION.md` - NATS integration guide
- `IMPLEMENTATION_STATUS.md` - Implementation tracking
- `PMOVESCHIT_DECODERv0.1.md` - Decoder specification
- `PMOVESCHIT_DECODER_MULTIv0.1.md` - Multi-modal decoder

**External References:**
- Nickel & Kiela (2017) - "Poincaré Embeddings for Learning Hierarchical Representations"
- Bromley et al. (2021) - "Riemann Zeta Function in Signal Processing"
- OpenAI CLIP - "Learning Transferable Visual Models From Natural Language Supervision"

---

**Document Version:** 1.0
**Last Updated:** 2026-02-08
**Status:** Production Ready
