# CGP Encoding Reference

**Layer:** L1 Protocol
**Status:** Current
**Last Updated:** 2026-03-11

> Field-by-field reference for constructing CHIT Geometry Packets (CGP v1.0). Includes JSON schema examples, validation rules, and construction patterns for each section of the packet.

---

## Table of Contents

1. [Packet Skeleton](#packet-skeleton)
2. [Root Fields](#root-fields)
3. [Meta Block](#meta-block)
4. [Signature Block](#signature-block)
5. [Super-Nodes](#super-nodes)
6. [Constellations](#constellations)
7. [Points](#points)
8. [MACA Consensus Block](#maca-consensus-block)
9. [Anchor Encryption Block](#anchor-encryption-block)
10. [Hyperbolic Encoding Block](#hyperbolic-encoding-block)
11. [Schema Versions](#schema-versions)
12. [Validation Checklist](#validation-checklist)
13. [Construction Examples](#construction-examples)
14. [JSON Schema Reference](#json-schema-reference)

---

## Packet Skeleton

Minimal valid CGP v1.0:

```json
{
  "spec": "chit.cgp.v1.0",
  "meta": {
    "source": "text",
    "units_mode": "sentences",
    "K": 4,
    "bins": 8,
    "backend": "sentence-transformers/all-MiniLM-L6-v2",
    "created_at": "2026-03-11T00:00:00Z"
  },
  "super_nodes": [
    {
      "id": "super_0",
      "label": "Mode 0",
      "constellations": [
        {
          "id": "const_0_0",
          "anchor": [0.1, -0.2, 0.3],
          "radial_minmax": [-0.5, 0.9],
          "spectrum": [0.25, 0.25, 0.25, 0.25, 0.0, 0.0, 0.0, 0.0]
        }
      ]
    }
  ]
}
```

---

## Root Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `spec` | string | **Yes** | Protocol version identifier |
| `meta` | object | **Yes** | Encoding metadata |
| `sig` | object | No | HMAC signature block |
| `super_nodes` | array | **Yes** | Top-level geometric clusters |

### `spec` Values

| Value | Status | Notes |
|-------|--------|-------|
| `chit.cgp.v1.0` | **Current** | Full production spec |
| `chit.cgp.v0.2` | Stable | Attribution + Merkle, no zeta |
| `chit.cgp.v0.1` | Legacy | Basic super_nodes only |

**Legacy aliases** (accepted but deprecated):
- `cgp.v1` maps to `chit.cgp.v1.0`
- `geometry.cgp.v1` maps to `chit.cgp.v1.0`

---

## Meta Block

```json
{
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
  }
}
```

### Field Details

| Field | Type | Required | Validation | Description |
|-------|------|----------|------------|-------------|
| `source` | enum | **Yes** | `docx\|text\|latent\|image\|audio\|video` | Content modality |
| `units_mode` | enum | **Yes** | `paragraphs\|sentences\|tokens\|frames\|samples` | Segmentation granularity |
| `K` | integer | **Yes** | 4-16 | Number of constellations |
| `bins` | integer | **Yes** | 5-12 | Spectrum histogram resolution |
| `backend` | string | **Yes** | — | Embedding model identifier |
| `mhep` | float | No | > 0 | Multi-scale Hyperbolic Entropy Product |
| `Hg_traj` | float[] | No | Monotonically decreasing | Global entropy trajectory |
| `Hs_traj` | float[] | No | Should stabilize | Slab entropy trajectory |
| `created_at` | string | No | ISO 8601 | Creation timestamp |
| `encoder_version` | string | No | semver | Encoder software version |
| `zeta_filtering` | boolean | No | — | Whether zeta filter was applied |

### Source-Backend Pairings

| Source | Recommended Backend | Dimensions |
|--------|-------------------|-----------|
| `text`, `docx` | `sentence-transformers/all-MiniLM-L6-v2` | 384 |
| `image` | `clip-ViT-B-32` | 512 |
| `audio` | `whisper-base` + `all-MiniLM-L6-v2` | 384 |
| `video` | `clip-ViT-B-32` + temporal pooling | 512 |
| `latent` | (pre-embedded, any) | varies |

---

## Signature Block

```json
{
  "sig": {
    "alg": "HMAC-SHA256",
    "kid": "9f86d081884c7d65",
    "ts": 1739001600,
    "hmac": "rTfzmOEHraWrVGjJW+tmEftsEXjl08dJmoi/gDCQfzo="
  }
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `alg` | string | **Yes** | Always `"HMAC-SHA256"` |
| `kid` | string | **Yes** | Key identifier: `sha256(passphrase)[:16]` |
| `ts` | integer | No | Unix timestamp of signing |
| `hmac` | string | **Yes** | Base64-encoded HMAC digest |

### Signing Process

1. Deep-copy the CGP document
2. Remove the `sig` field if present
3. Canonicalize: `json.dumps(doc, sort_keys=True, separators=(",", ":"))`
4. Compute: `hmac.new(passphrase.encode(), canonical.encode(), sha256).digest()`
5. Base64-encode the digest
6. Attach `sig` block

### Verification Process

1. Extract and save `sig` block
2. Remove `sig` from document
3. Re-canonicalize with same parameters
4. Re-compute HMAC with known passphrase
5. Constant-time compare with `sig.hmac`

---

## Super-Nodes

Super-nodes are the top-level geometric clusters. A CGP has 1 to K super-nodes.

```json
{
  "id": "super_0",
  "label": "Resonant Mode 0",
  "summary": "Economic transactions and token distribution patterns",
  "x": -212.3,
  "y": 148.1,
  "r": 260.0,
  "hyperbolic": {
    "poincare": [0.1, -0.05],
    "curvature": -1.0
  },
  "constellations": [ ... ]
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | **Yes** | Unique identifier (e.g., `"super_0"`) |
| `label` | string | No | Human-readable label |
| `summary` | string | No | Descriptive summary of the cluster |
| `x` | float | No | 2D visualization X coordinate |
| `y` | float | No | 2D visualization Y coordinate |
| `r` | float | No | Visualization radius |
| `hyperbolic` | object | No | Poincare disk encoding (see [Hyperbolic Block](#hyperbolic-encoding-block)) |
| `constellations` | array | **Yes** | Child constellation clusters |

### ID Conventions

- Super-nodes: `super_{index}` (e.g., `super_0`, `super_1`)
- Constellations: `const_{super}_{index}` (e.g., `const_0_0`, `const_0_1`)
- Points: `pt_{super}_{const}_{index}` (e.g., `pt_0_0_0`)

---

## Constellations

Constellations are the core geometric unit — each represents a semantically coherent cluster defined by an anchor vector and energy spectrum.

```json
{
  "id": "const_0_0",
  "label": "Token Distribution",
  "summary": "Weekly GroToken allocation patterns",
  "anchor": [0.012, -0.31, 0.82, 0.15, -0.07, 0.44, 0.11, -0.22],
  "radial_minmax": [-0.45, 0.93],
  "spectrum": [0.08, 0.11, 0.15, 0.22, 0.18, 0.12, 0.08, 0.06],
  "spectrum_zeta": [0.09, 0.12, 0.16, 0.23, 0.17, 0.11, 0.07, 0.05],
  "points": [ ... ],
  "maca_consensus": { ... },
  "anchor_enc": { ... }
}
```

| Field | Type | Required | Validation | Description |
|-------|------|----------|------------|-------------|
| `id` | string | **Yes** | Unique within CGP | Constellation identifier |
| `label` | string | No | — | Human-readable label |
| `summary` | string | No | — | Topic keywords or description |
| `anchor` | float[] | **Yes*** | L2 norm = 1.0 | Unit vector defining the cluster direction |
| `radial_minmax` | [float, float] | **Yes** | min < max | Projection bounds [min, max] |
| `spectrum` | float[] | **Yes** | Length = meta.bins, sum = 1.0 | Energy distribution histogram |
| `spectrum_zeta` | float[] | No | Length = meta.bins | Zeta-filtered spectrum |
| `points` | array | No | — | Individual data points |
| `maca_consensus` | object | No | — | Multi-agent consensus data |
| `anchor_enc` | object | No | — | Encrypted anchor (replaces `anchor`) |

*`anchor` is required unless `anchor_enc` is provided.

### Anchor Validation

```python
import numpy as np

anchor = np.array(constellation["anchor"])
assert abs(np.linalg.norm(anchor) - 1.0) < 1e-6, "Anchor must be unit vector"
```

### Spectrum Validation

```python
spectrum = constellation["spectrum"]
assert len(spectrum) == cgp["meta"]["bins"], "Spectrum length must match meta.bins"
assert abs(sum(spectrum) - 1.0) < 1e-6, "Spectrum must sum to 1.0"
assert all(v >= 0 for v in spectrum), "Spectrum values must be non-negative"
```

---

## Points

Individual content units within a constellation.

```json
{
  "id": "pt_0_0_0",
  "x": 13.4,
  "y": -8.2,
  "proj": 0.83,
  "conf": 0.94,
  "text": "Weekly token distribution shows stable growth patterns",
  "text_b64": "V2Vla2x5IHRva2VuIGRpc3Ry...",
  "char_len": 55,
  "word_count": 8,
  "contributor_id": "agent-zero",
  "merkle_proof": ["a1b2c3...", "d4e5f6..."],
  "weight": 0.85
}
```

| Field | Type | Required | Validation | Description |
|-------|------|----------|------------|-------------|
| `id` | string | **Yes** | Unique within CGP | Point identifier |
| `x` | float | No | — | 2D visualization X |
| `y` | float | No | — | 2D visualization Y |
| `proj` | float | Recommended | Within `radial_minmax` | Projection onto anchor |
| `conf` | float | Recommended | [0.0, 1.0] | Assignment confidence |
| `text` | string | No | — | Original text content |
| `text_b64` | string | No | Valid base64 | Base64-encoded text |
| `char_len` | integer | No | > 0 | Character count |
| `word_count` | integer | No | > 0 | Word count |
| `contributor_id` | string | No | — | Who contributed this unit |
| `merkle_proof` | string[] | No | Valid hash chain | Merkle proof path |
| `weight` | float | No | [0.0, 1.0] | Dirichlet attribution weight |

### Projection Validation

```python
proj = point["proj"]
rmin, rmax = constellation["radial_minmax"]
assert rmin <= proj <= rmax, f"Projection {proj} outside [{rmin}, {rmax}]"
```

### Text Encoding

Either `text` or `text_b64` (or both) may be present:
- `text`: UTF-8 string, human-readable
- `text_b64`: Base64-encoded UTF-8 bytes, preferred for binary-safe transport
- If both present, `text_b64` takes precedence

### Merkle Proof Structure

The `merkle_proof` array contains sibling hashes from leaf to root:

```
proof[0] = sibling of leaf
proof[1] = sibling of parent
...
proof[n-1] = sibling of root's child
```

Verification: iteratively hash (leaf, proof[0]), then (result, proof[1]), etc. Final result should equal the constellation's merkle_root.

---

## MACA Consensus Block

Multi-Agent Consensus via Aggregation — records how multiple agents agreed on constellation assignment.

```json
{
  "maca_consensus": {
    "entropy_delta": 0.34,
    "votes": [3, 4, 2],
    "confidence": 0.85
  }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `entropy_delta` | float | Entropy change from consensus (should be negative = more agreement) |
| `votes` | integer[] | Vote counts per round |
| `confidence` | float | Final consensus confidence [0, 1] |

### MACA Process

1. Multiple agents independently assign content units to constellations
2. Votes are aggregated across rounds
3. Entropy delta measures information gain from consensus
4. Confidence = fraction of agents agreeing on final assignment

---

## Anchor Encryption Block

When confidentiality is required, the `anchor` field is replaced with `anchor_enc`:

```json
{
  "anchor_enc": {
    "alg": "AES-GCM",
    "iv": "YmFzZTY0X2l2X2hlcmU=",
    "salt": "YmFzZTY0X3NhbHRfaGVyZQ==",
    "ct": "YmFzZTY0X2NpcGhlcnRleHQ="
  }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `alg` | string | Always `"AES-GCM"` |
| `iv` | string | Base64-encoded initialization vector (12 bytes) |
| `salt` | string | Base64-encoded PBKDF2 salt (16 bytes) |
| `ct` | string | Base64-encoded ciphertext (anchor + 16-byte auth tag) |

### Key Derivation

```python
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

kdf = PBKDF2HMAC(
    algorithm=hashes.SHA256(),
    length=32,
    salt=salt_bytes,
    iterations=100_000
)
key = kdf.derive(passphrase.encode())
```

### Encryption

```python
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

aesgcm = AESGCM(key)
ciphertext = aesgcm.encrypt(iv, anchor_json_bytes, None)
```

### Decryption

```python
plaintext = aesgcm.decrypt(iv, ciphertext, None)
anchor = json.loads(plaintext)
```

---

## Hyperbolic Encoding Block

Poincare disk coordinates for hierarchical positioning.

```json
{
  "hyperbolic": {
    "poincare": [0.1, -0.05],
    "curvature": -1.0
  }
}
```

| Field | Type | Validation | Description |
|-------|------|------------|-------------|
| `poincare` | [float, float] | `sqrt(x^2 + y^2) < 1.0` | Poincare disk coordinates |
| `curvature` | float | Always -1.0 | Sectional curvature |

### Coordinate Constraints

```python
x, y = hyperbolic["poincare"]
r = math.sqrt(x**2 + y**2)
assert r < 1.0, "Point must be inside the Poincare disk"
assert r < 0.95, "Recommended: stay below 0.95 for numerical stability"
```

---

## Schema Versions

### v1.0 (Current Production)

Full spec with all fields documented above. Key additions over v0.2:
- `spectrum_zeta` field
- `maca_consensus` block
- `hyperbolic` block
- `encoder_version` in meta
- `zeta_filtering` flag in meta

JSON Schema: `pmoves/contracts/schemas/geometry/cgp.v1.schema.json`

### v0.2 (Stable)

Attribution weights and Merkle proofs. Missing:
- Zeta-filtered spectrum
- MACA consensus
- Hyperbolic encoding
- Encoder version tracking

### v0.1 (Legacy)

Basic super_nodes and constellations. Missing:
- Attribution (no weights, no Merkle proofs)
- Security (no signature block)
- Metadata (minimal meta block)

### Migration Path

```
v0.1 → v0.2: Add points[].weight, points[].merkle_proof, sig block
v0.2 → v1.0: Add spectrum_zeta, maca_consensus, hyperbolic, meta extensions
```

---

## Validation Checklist

Before publishing a CGP v1.0 packet:

- [ ] `spec` is `"chit.cgp.v1.0"`
- [ ] `meta.source` is a valid enum value
- [ ] `meta.units_mode` is a valid enum value
- [ ] `meta.K` matches number of constellations across all super_nodes
- [ ] `meta.bins` matches length of all `spectrum` arrays
- [ ] All `anchor` vectors have L2 norm = 1.0 (tolerance: 1e-6)
- [ ] All `spectrum` arrays sum to 1.0 (tolerance: 1e-6)
- [ ] All `spectrum` values are non-negative
- [ ] All `points[].proj` values within their constellation's `radial_minmax`
- [ ] All `points[].conf` values in [0.0, 1.0]
- [ ] All IDs are unique within the packet
- [ ] `sig.hmac` is valid if signature block present
- [ ] `anchor_enc` replaces `anchor` (never both present)
- [ ] `hyperbolic.poincare` coordinates within unit disk (r < 1.0)
- [ ] `created_at` is valid ISO 8601

---

## Construction Examples

### Python: Full CGP Construction

> **Note:** This example illustrates the designed pipeline flow. `ConstellationHarvest` and
> `ZetaSpectralFilter` are planned modules — see the
> [pipeline walkthrough](MATH_PIPELINE_WALKTHROUGH.md) for current implementation status.

```python
import json
import numpy as np
from datetime import datetime, timezone
from pmoves.tools.chr import ConstellationHarvest
from pmoves.tools.zeta_filter import ZetaSpectralFilter
from pmoves.tools.chit_security import sign_cgp

# 1. Embed content
embeddings = model.encode(texts, normalize_embeddings=True)

# 2. Run CHR
chr = ConstellationHarvest(K=8, bins=8)
U = chr.optimize_anchors(embeddings)
p = chr.compute_assignments(embeddings, U)
spectra = chr.compute_spectra(embeddings, U, p, bins=8)
Hg, Hs = chr.compute_entropy_trajectory(embeddings, U, p)

# 3. Zeta filter
zeta = ZetaSpectralFilter(num_zeros=10)
spectra_zeta = [zeta.filter_spectrum(s) for s in spectra]

# 4. Construct CGP
cgp = {
    "spec": "chit.cgp.v1.0",
    "meta": {
        "source": "text",
        "units_mode": "sentences",
        "K": 8,
        "bins": 8,
        "backend": "sentence-transformers/all-MiniLM-L6-v2",
        "mhep": float(Hg[-1] * Hs[-1]),
        "Hg_traj": [float(h) for h in Hg],
        "Hs_traj": [float(h) for h in Hs],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "encoder_version": "1.0.0",
        "zeta_filtering": True
    },
    "super_nodes": []
}

for k in range(8):
    assigned = np.where(p[:, k] > 0.5)[0]
    projections = embeddings[assigned] @ U[k]
    rmin, rmax = float(projections.min()), float(projections.max())

    constellation = {
        "id": f"const_0_{k}",
        "anchor": U[k].tolist(),
        "radial_minmax": [rmin, rmax],
        "spectrum": spectra[k].tolist(),
        "spectrum_zeta": spectra_zeta[k].tolist(),
        "points": [
            {
                "id": f"pt_0_{k}_{j}",
                "proj": float(projections[j]),
                "conf": float(p[assigned[j], k]),
                "text": texts[assigned[j]]
            }
            for j in range(len(assigned))
        ]
    }

    if k == 0:
        cgp["super_nodes"].append({
            "id": "super_0",
            "label": "Primary Mode",
            "constellations": [constellation]
        })
    else:
        cgp["super_nodes"][0]["constellations"].append(constellation)

# 5. Sign
cgp = sign_cgp(cgp, passphrase="shared-secret")
```

### TypeScript: Using createCHITSystem

```typescript
import { createCHITSystem } from '@pmoves/chit';

const chit = createCHITSystem({
  dirichlet: { smoothingAlpha: 0.1, concentrationK: 1.0, decayHalfLife: 12 },
  hyperbolic: { curvature: -1, baseRadius: 0.3 },
  merkle: { strategy: 'per_week' },
  cgp: { namespace: 'pmoves.tokenism' },
  swarm: { optimizationTarget: 'gini_reduction' }
});

// Record actions
chit.attribution.recordAction({
  address: '0xABC...',
  action: 'spending',
  amount: 50,
  week: 12,
  category: 'groceries'
});

// Generate weekly CGP
const cgp = chit.generator.generateWeeklyCGP(weekData, chit.attribution);

// Publish
await chit.publisher.publishWeeklyCGP(12, cgp, { gini: 0.42 });
```

---

## JSON Schema Reference

### Location

```
pmoves/contracts/schemas/geometry/
  cgp.v1.schema.json        # CGP v1.0 full schema
  cgp.v2.schema.json        # CGP v2.0 (draft, extends v1.0)
  swarm.meta.v1.schema.json # EvoSwarm parameter pack schema
```

### Usage

```python
import jsonschema, json

with open("pmoves/contracts/schemas/geometry/cgp.v1.schema.json") as f:
    schema = json.load(f)

jsonschema.validate(cgp, schema)  # Raises ValidationError on failure
```

---

## Cross-References

- [MATH_PIPELINE_WALKTHROUGH.md](MATH_PIPELINE_WALKTHROUGH.md) — End-to-end pipeline narrative
- [CALIBRATION_GUIDE.md](CALIBRATION_GUIDE.md) — Decoder calibration procedures
- [CGP_v1.0_SPECIFICATION.md](CGP_v1.0_SPECIFICATION.md) — Official wire format spec
- [GEOMETRY_BUS_INTEGRATION.md](GEOMETRY_BUS_INTEGRATION.md) — NATS transport guide

---

*This document is a living artifact tracked by [CHIT_CHANGE_TRACKER.md](../CHIT_CHANGE_TRACKER.md).*
