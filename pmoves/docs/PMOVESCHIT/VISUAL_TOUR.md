# CHIT — A Visual Tour of PMOVES.AI

> **From boundary geometry to working packets.** This tour walks you through CHIT (Cymatic Holographic Information Theory) as it actually exists in the codebase — not as theory, but as code you can run.

**Assumptions:** You know what a vector embedding is. Everything else gets explained.

---

## Tour Map

```
1. What CHIT Actually Is (5 min)       → The problem it solves
2. The CGP Packet (10 min)              → Structure, fields, real JSON
3. Encoding Flow (10 min)               → docx → anchor → spectrum → CGP
4. Terminal Visualization (5 min)       → Run it yourself
5. Gateway API (10 min)                 → Ingest, decode, calibrate endpoints
6. Security Layer (5 min)               → HMAC signatures, anchor encryption
7. Geometry Bus (5 min)                → NATS integration, shape stores
8. Cross-Service Tour (10 min)         → Where CHIT touches everything
```

---

## 1. What CHIT Actually Is

### The Problem

```
User says "bank"  →  AI sees: bank (financial) | bank (river) | bank (pool) | bank (storage)
                   →  Token carries no context about WHICH bank is meant
                   →  Pay for tokens, get ambiguity
```

CHIT encodes meaning as **geometry** instead of tokens. A "shape packet" can reconstruct the same meaning on the other side — fewer bits, less drift.

### The Core Insight

> **Information has geometry.** When you embed sentences into a vector space, they cluster. CHIT captures those clusters as packets and throws away the raw tokens.

Think of it like a star chart:
- You don't transmit every photon — you record positions and brightnesses
- Anyone with a telescope sees the same constellations
- The chart is smaller, but captures the essential structure

### Why "Holographic"?

The holographic principle in physics: information inside a volume can be fully described by data on its boundary. CHIT works the same way:

```
High-dimensional embedding cloud (the "volume")
    ↓
Encoded as anchors + spectra (the "boundary")
    ↓
Boundary is smaller, but captures essential structure
```

---

## 2. The CGP Packet

### What is a CGP?

**C**ymatic-**G**eometry **P**acket. A JSON document that describes meaning as geometric boundaries.

### CGP v1.0 Structure

```json
{
  "spec": "chit.cgp.v1.0",
  "meta": {
    "source": "text",
    "units_mode": "paragraphs",
    "K": 8,
    "bins": 8,
    "backend": "sentence-transformers/all-MiniLM-L6-v2"
  },
  "super_nodes": [
    {
      "id": "super_0",
      "constellations": [
        {
          "id": "urban_farming",
          "anchor": [0.42, -0.18, 0.67, 0.31],
          "radial_minmax": [-0.22, 0.85],
          "spectrum": [0.10, 0.35, 0.40, 0.15],
          "points": [...]
        }
      ]
    }
  ]
}
```

### Field Dictionary

| Field | Type | Meaning |
|-------|------|---------|
| `spec` | string | CGP version identifier |
| `meta` | object | Encoding metadata (backend, K, bins, mode) |
| `super_nodes` | array | Major semantic regions ("continents") |
| `constellations` | array | Clusters within each region ("weather systems") |
| `anchor` | float[] | Direction vector in embedding space (the "where") |
| `radial_minmax` | float[2] | Projection range along the anchor (the "range") |
| `spectrum` | float[] | Energy histogram — how much density in each bin |
| `points` | array | Optional raw data (text, coordinates, confidence) |

### Analogy: Weather Map

| CGP Concept | Weather Analogy |
|-------------|-----------------|
| Super node | Continent |
| Constellation | Weather system |
| Anchor | Wind direction |
| Spectrum | Pressure distribution along direction |
| Points | Actual weather stations |

### Real CGP from the Codebase

From `pmoves/services/gateway/gateway/api/chit.py`:

```python
class Point(BaseModel):
    id: Optional[str] = None
    modality: Optional[str] = None
    ref_id: Optional[str] = None
    x: Optional[float] = None
    y: Optional[float] = None
    proj: Optional[float] = None
    conf: Optional[float] = None
    text: Optional[str] = None
    source_ref: Optional[str] = None

class Constellation(BaseModel):
    id: str
    anchor: Optional[List[float]] = None
    anchor_enc: Optional[Dict[str, Any]] = None  # Encrypted variant
    summary: Optional[str] = None
    radial_minmax: List[float]
    spectrum: List[float]
    points: List[Point] = Field(default_factory=list)

class SuperNode(BaseModel):
    id: str
    constellations: List[Constellation]

class CGP(BaseModel):
    spec: str
    meta: Dict[str, Any]
    super_nodes: List[SuperNode]
    sig: Optional[Dict[str, Any]] = None  # HMAC signature
```

---

## 3. Encoding Flow

### The Pipeline

```
Document (.docx, .txt, raw text)
    ↓
Units (paragraphs, sentences, or custom)
    ↓
Embed (sentence-transformers/all-MiniLM-L6-v2)
    ↓
CHR (Constellation Harvest Regularization)
    ↓
CGP (CHIT Geometry Packet)
```

### Step 1: Document → Units

From `pmoves/tools/chit_backend.py`:

```python
def build_cgp_from_docx(docx_path: str,
                         units_mode="paragraphs",
                         K=8, iters=30, beta=12.0, bins=8, tau=5.0, seed=42,
                         S=3):
    # 1) Load & split
    paras = chrmod.read_docx_any(docx_path)
    units = chrmod.paragraphs_to_units(paras, mode=units_mode)
```

### Step 2: Units → Embeddings

```python
    # 2) Embed
    Z, backend = chrmod.embed_texts(units, prefer_sentence_transformer=True)
```

`Z` is now a matrix of N vectors × D dimensions (384 for MiniLM-L6-v2).

### Step 3: CHR Optimization

```python
    # 3) Optimize CHR — find anchor directions
    U, p, Hg_traj, Hs_traj = chrmod.chr_optimize(
        Z, K=int(K), iters=int(iters), beta=float(beta),
        bins=int(bins), tau=float(tau), seed=int(seed)
    )
```

| Variable | Shape | Meaning |
|----------|-------|---------|
| `Z` | N × D | Embedding matrix |
| `U` | K × D | K anchor directions |
| `p` | N × K | Soft assignment probabilities |
| `Hg_traj` | iters | Global entropy trajectory |
| `Hs_traj` | iters | Slab entropy trajectory |

### Step 4: Build CGP

```python
    # 4) 2D layout for visualization
    pca = PCA(n_components=2, random_state=0)
    Z2 = pca.fit_transform(Z)
    U2 = pca.transform(U)

    # 5) Summaries per constellation
    df, summaries = chrmod.structure_outputs(units, Z, U, p)

    # 6) Group anchors into super-nodes
    S = min(S, U.shape[0])
    sup_labels = KMeans(n_clusters=S, n_init=10, random_state=seed).fit_predict(U)

    # 7) Build CGP JSON
    cgp = {
        "spec": "chit.cgp.v0.1",
        "meta": {
            "source": "docx",
            "units_mode": units_mode,
            "K": int(K),
            "bins": int(bins),
            "mhep": float(chrmod.compute_mhep(Hg_traj, Hs_traj, K=int(K), bins=int(bins))),
            "Hg_traj": [float(x) for x in Hg_traj],
            "Hs_traj": [float(x) for x in Hs_traj],
            "backend": backend
        },
        "super_nodes": supers
    }
```

### The Soft Spectrum

For each constellation, compute a soft histogram of projections:

```python
def _soft_spectrum(proj_vals, bins=8, tau=5.0):
    v = np.asarray(proj_vals, dtype=float)
    tmin, tmax = float(v.min()), float(v.max())
    centers = np.linspace(tmin, tmax, bins)
    # Soft assignment (Gaussian kernel)
    dist2 = (v[:, None] - centers[None, :]) ** 2
    weights = np.exp(-tau * dist2)
    weights = weights / (weights.sum(axis=1, keepdims=True) + 1e-9)
    hist = weights.mean(axis=0)
    return (hist / (hist.sum() + 1e-9)).tolist()
```

---

## 4. Terminal Visualization

### Run It

```bash
# Sparkline mode
echo '{"values": [0.1, 0.3, 0.5, 0.4, 0.8, 0.9, 0.7]}' | python pmoves/tools/chit_terminal_viz.py --mode sparkline

# Bar chart mode
echo '{"labels": ["factual", "conceptual", "procedural"], "values": [0.85, 1.2, 0.3]}' | python pmoves/tools/chit_terminal_viz.py --mode bar

# CGP summary (demo mode)
python pmoves/tools/chit_terminal_viz.py --mode cgp

# Poincaré disk (hyperbolic geometry)
echo '{"points": [[0.3, -0.4]], "labels": ["content"]}' | python pmoves/tools/chit_terminal_viz.py --mode poincare
```

### What You Get

```
╔══════════════════════════════════════╗
║     CGP v2 Packet Summary            ║
╚══════════════════════════════════════╝

  Spectral:  ▁▂▃▅▇█

  Dirichlet Weights:
    factual       ████████░░░░░░░░░░░░░░  0.850
    conceptual    ██████████████████░░░  1.200
    procedural    █████░░░░░░░░░░░░░░░░░  0.300

  Poincaré Disk (hyperbolic space)
    · · · · · · · · · · · · · · · · · · ·
    · · · · · · · · · · · · · · · · · · ·
    · · · · · · · · · · ● · · · · · · · ·
    · · · · · · · · · · · · · · · · · · ·
    · · · · · · · · · · · · · · · · · · ·
```

### Visualization Code

From `pmoves/tools/chit_terminal_viz.py`:

```python
SPARK_CHARS = " ▁▂▃▄▅▆▇█"

def sparkline(values: List[float], width: Optional[int] = None) -> str:
    if not values:
        return ""

    if width and len(values) > width:
        step = len(values) / width
        values = [values[int(i * step)] for i in range(width)]

    min_v = min(values)
    max_v = max(values)
    span = max_v - min_v if max_v != min_v else 1

    chars = []
    for v in values:
        idx = int((v - min_v) / span * (len(SPARK_CHARS) - 1))
        chars.append(SPARK_CHARS[idx])
    return "".join(chars)

def poincare_disk(
    points: List[Tuple[float, float]],
    size: int = 21,
    labels: Optional[List[str]] = None,
) -> str:
    """Render Poincare disk visualization in terminal.
    
    Maps hyperbolic coords [-1, 1] to character grid.
    """
    grid = [[" " for _ in range(size * 2)] for _ in range(size)]
    center_x = size
    center_y = size // 2
    radius = min(center_x, center_y) - 1

    # Draw disk boundary
    for angle in range(360):
        rad = math.radians(angle)
        gx = int(center_x + radius * math.cos(rad) * 2)
        gy = int(center_y + radius * math.sin(rad))
        if 0 <= gy < size and 0 <= gx < size * 2:
            grid[gy][gx] = "·"

    # Plot points
    point_chars = "●○◆◇■□▲△★☆"
    for i, (px, py) in enumerate(points):
        gx = int(center_x + px * radius * 2)
        gy = int(center_y + py * radius)
        if 0 <= gy < size and 0 <= gx < size * 2:
            char = point_chars[i % len(point_chars)]
            grid[gy][gx] = char

    return "\n".join(lines)
```

---

## 5. Gateway API

### Endpoints

From `pmoves/services/gateway/gateway/api/chit.py`:

```
POST /geometry/event      → Ingest a CGP
GET  /shape/point/{pid}/jump → Jump to a point's source
POST /geometry/decode/text  → Decode geometry back to text
POST /geometry/calibration/report → Calibration quality report
```

### Ingest Endpoint

```python
@router.post("/geometry/event")
def geometry_event(event: GeometryEventEnvelope):
    if event.type not in _ACCEPTED_EVENT_TYPES:
        raise HTTPException(status_code=400, detail="Unsupported geometry event type")
    shape_id = ingest_cgp(event.data.model_dump())
    return {"ok": True, "shape_id": shape_id, "event": event.type}
```

The `ingest_cgp` function:
1. Verifies HMAC signature (if `CHIT_REQUIRE_SIGNATURE=true`)
2. Decrypts encrypted anchors (if `CHIT_DECRYPT_ANCHORS=true`)
3. Computes shape ID from canonical CGP
4. Stores in ShapeStore
5. Persists to `data/{shape_id}.json`
6. Syncs to Supabase (if configured)
7. Emits NATS event

### Decode Endpoint

```python
@router.post("/geometry/decode/text")
def geometry_decode_text(body: GeometryDecodeTextRequest):
    # Load constellations from ShapeStore
    # Project codebook entries onto anchor
    # Match spectrum distribution
    # Return best-scoring entries
```

```python
def decode_constellations(
    constellations: Sequence[Constellation],
    per_constellation: int = 10,
    codebook_path: Optional[str] = None,
) -> Dict[str, Any]:
    items = _load_codebook(codebook_path)
    out: List[Dict[str, Any]] = []
    
    for const in constellations:
        anchor = const.anchor
        nrm = sum(x * x for x in anchor) ** 0.5 or 1.0
        u = [x / nrm for x in anchor]
        
        # Project all codebook entries onto anchor
        projs = []
        for idx, it in enumerate(items):
            vec = it.get("vec")
            if vec:
                proj = sum(a * b for a, b in zip(u, vec))
                projs.append((idx, proj))
        
        # Match against spectrum
        rmin, rmax = const.radial_minmax
        bins = len(const.spectrum)
        centers = [rmin + (rmax - rmin) * i / max(1, bins - 1) for i in range(bins)]
        
        sel: List[tuple[int, float, float]] = []
        for idx, proj in projs:
            nearest = min(range(bins), key=lambda i: abs(proj - centers[i]))
            w = const.spectrum[nearest]
            sel.append((idx, w, proj))
        
        sel.sort(key=lambda x: x[1], reverse=True)
        for idx, w, proj in sel[:per_constellation]:
            out.append({
                "constellation_id": const.id,
                "text": items[idx].get("text"),
                "proj_est": proj,
                "score": w,
            })
    
    return {"items": out}
```

### Calibration Endpoint

```python
@router.post("/geometry/calibration/report")
def geometry_calibration_report(body: GeometryCalibrationRequest):
    # Compute KL divergence between target spectrum and empirical
    # Compute JS divergence
    # Calculate coverage (fraction of bins with data)
    # Write report to artifacts/reconstruction_report.md
```

```python
def kl(p, q): 
    eps = 1e-9
    return sum(pi * (math.log((pi + eps) / (qi + eps))) for pi, qi in zip(p, q))

def js(p, q):
    m = [(pi + qi) / 2 for pi, qi in zip(p, q)]
    return 0.5 * kl(p, m) + 0.5 * kl(q, m)

cov = sum(1 for e in emp if e > 0) / bins
return {"KL": kl(tgt, emp), "JS": js(tgt, emp), "coverage": cov}
```

---

## 6. Security Layer

### HMAC Signatures

CGPs can be signed for tamper-proof provenance. The security module in `pmoves/tools/chit_security.py`:

```python
from pmoves.tools.chit_security import sign_cgp, verify_cgp

# Sign a CGP
signed_cgp = sign_cgp(cgp, passphrase="your_secret", kid="chit-signing-v01")

# Verify a signed CGP
is_valid = verify_cgp(signed_cgp, passphrase="your_secret")
```

**Key separation:** The system supports separate keys for signing vs encryption:
- `CHIT_SIGNING_KEY` — for HMAC signatures (recommended)
- `CHIT_ENCRYPTION_KEY` — for anchor encryption
- `CHIT_PASSPHRASE` — legacy fallback (same key for both)

### Canonical JSON

From `pmoves/tools/chit_common.py`:

```python
def canon(obj: Dict[str, Any]) -> bytes:
    """Create canonical JSON representation for signing.
    
    Uses deterministic JSON with sorted keys and minimal whitespace
    to ensure consistent hashing across platforms.
    """
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")
```

### Anchor Encryption

Anchors can be encrypted to protect sensitive geometry:

```python
from pmoves.tools.chit_security import encrypt_anchors, decrypt_anchors

# Encrypt all anchors in a CGP
encrypted_cgp = encrypt_anchors(cgp, passphrase="your_secret")

# Decrypt in place
decrypted_cgp = decrypt_anchors(encrypted_cgp, passphrase="your_secret")
```

**Encryption flow:**
1. Derive key from passphrase + random salt (PBKDF2, 600k iterations, SHA-256)
2. Pack anchor floats as binary (float32 array with length prefix)
3. Encrypt with AES-GCM (authenticated encryption)
4. Store as base64: `{iv, salt, ct}`

### Graph Linker Integration

From `pmoves/services/graph-linker/chit_signer.py`:

```python
from pmoves.services.graph-linker.chit_signer import sign_neo4j_node, verify_neo4j_node

# Node signing is gated by CHIT_SIGN_NEO4J env var
# When disabled (default), returns node unchanged
signed_node = sign_neo4j_node(node_data)

# Verification for incoming nodes
is_valid = verify_neo4j_node(signed_node)
```

**Design principle:** Signing is additive. Existing functionality is never broken when signing is off.

---

## 7. Geometry Bus & ShapeStore

### ShapeStore

In-memory LRU cache for geometry packets (`pmoves/services/common/shape_store.py`):

```python
from pmoves.services.common.shape_store import ShapeStore

# Initialize with capacity
store = ShapeStore(capacity=10_000)

# Ingest a CGP
store.put_cgp(cgp)

# Look up a constellation
constellation = store.get_constellation("urban_farming")

# Jump to source
locator = store.jump_locator("p:abc123:0")
# → {"modality": "video", "ref_id": "yt123", "t": 31.25}
```

**Features:**
- Thread-safe LRU cache with configurable capacity
- Cross-modal jump locators (video, audio, text)
- Optional warm from Supabase (fetches recent constellations)
- Supports both `chit.cgp.v0.2` and legacy `geometry.cgp.v1`

### NATS Integration

The geometry bus carries shape-encoded packets via NATS subjects:

```
geometry.cgp.v1    → CGP ingestion events
tokenism.>         → Tokenism simulator events
```

From `pmoves/docs/CHIT_TOOLS_CATALOG.md`:

| Subject | Purpose |
|---------|---------|
| `geometry.cgp.v1` | CGP ingestion events |
| `tokenism.sign.v1` | Tokenism signing events |
| `geometry.decode.text` | Decode request channel |

### Gateway Ingest Flow

```python
def ingest_cgp(cgp: Dict[str, Any]) -> str:
    # 1. Verify HMAC signature (if CHIT_REQUIRE_SIGNATURE=true)
    if CHIT_REQUIRE_SIGNATURE and not verify_hmac(cgp):
        raise HTTPException(status_code=400, detail="Invalid or missing HMAC signature")

    # 2. Decrypt encrypted anchors (if CHIT_DECRYPT_ANCHORS=true)
    for s in cgp.get("super_nodes", []) or []:
        for const in s.get("constellations", []) or []:
            decrypt_anchor(const)

    # 3. Compute shape ID from canonical CGP
    shape_id = compute_shape_id(cgp)

    # 4. Assign point IDs
    point_idx = 0
    for s in cgp.get("super_nodes", []) or []:
        for const in s.get("constellations", []) or []:
            for p in const.get("points", []) or []:
                if not p.get("id"):
                    p["id"] = f"p:{shape_id}:{point_idx}"
                    point_idx += 1

    # 5. Store in ShapeStore
    shape_store.on_geometry_event({"type": CGP_SPEC_VERSION, "data": cgp})

    # 6. Persist to disk
    _shape_path.write_text(json.dumps(cgp, indent=2))

    # 7. Sync to Supabase (if configured)
    supa.publish_cgp(shape_id, cgp)

    # 8. Emit NATS event
    emit_event({"type": "geometry.event", "shape_id": shape_id})

    return shape_id
```

### Jump Locator

Map a point back to its source material:

```python
@router.get("/shape/point/{pid}/jump")
def shape_point_jump(pid: str):
    loc = shape_store.jump_locator(pid)
    if not loc:
        # Handle video timestamps (v:yt123#t=31.25-45.0)
        if pid.startswith("v:") and "#t=" in pid:
            vid, t = pid[2:].split("#t=", 1)
            t0 = t.split("-")[0]
            return {
                "ok": True,
                "locator": {"modality": "video", "ref_id": vid, "t": float(t0)},
            }
        raise HTTPException(status_code=404, detail="point not found")
    return {"ok": True, "locator": loc}
```

### Supabase Warm

Load recent CGPs from Supabase on startup:

```python
async def warm_from_db(self, rest_url: Optional[str] = None, limit: int = 64) -> int:
    """Fetch recent constellations from Supabase.
    
    Tries tables in order: geometry_cgp_packets, geometry_cgp_v1, constellations
    """
    # ...
    count = 0
    for cgp in cgps:
        self.put_cgp(cgp)
        count += 1
    return count
```

---

## 8. Cross-Service Tour

### Where CHIT Lives

```
pmoves/
├── tools/
│   ├── chit_backend.py           # CGP generation from documents
│   ├── chit_terminal_viz.py      # Terminal visualization
│   ├── chit_common.py            # Canonical JSON for signing
│   ├── chit_security.py          # HMAC verification, decryption
│   ├── chit_encode_hook.py       # Hook for encoding
│   └── chit_verify.py           # Verification utilities
├── services/
│   ├── gateway/gateway/api/chit.py    # REST endpoints
│   ├── graph-linker/chit_signer.py    # Graph signing
│   ├── tokenism-simulator/services/chit_encoder.py
│   └── flute-gateway/chit_signing.py  # Flute integration
├── ui/lib/chit.ts                # Frontend CHIT utilities
└── integrations/
```

### CHIT Integration Status

| Service | Status | Role |
|---------|--------|------|
| Hi-RAG v2 | Full | ShapeStore for retrieval |
| Agent Zero | Full | MCP integration |
| Tokenism Simulator | Full | Encoding and signing |
| Gateway | Full | REST API |
| Graph Linker | Partial | Signing |
| Flute Gateway | Partial | Signing |
| Cipher MCP | None | — |
| Consciousness | None | — |

### Five Pillars

CHIT rests on five mathematical foundations:

| Pillar | Math | CHIT Hook |
|--------|------|-----------|
| **Dirichlet Distributions** | Conjugate prior for multinomial | `dirichlet-weights.ts` |
| **Hyperbolic Geometry** | Poincare disk, K=-1 | `hyperbolic-encoder.ts` |
| **Merkle Proofs** | SHA-256, inclusion proofs | `shape-attribution.ts` |
| **Zeta Spectral Filtering** | Gaussian kernels at zeta zeros | `zeta-filter.ts` |
| **EVO SWARM** | Evolutionary optimization | `swarm-attribution.ts` |

---

## Quick Reference

### CLI Cheat Sheet

```bash
# Generate CGP from docx
python pmoves/tools/chit_backend.py yourfile.docx --out cgp.json --K 8 --S 3

# Terminal visualization
python pmoves/tools/chit_terminal_viz.py --mode cgp --input cgp.json

# Run tests
pytest pmoves/tests/test_chit_security.py -v

# Encode with passphrase
CHIT_PASSPHRASE=your_secret python pmoves/tools/chit_encode_secrets.py

# Decode geometry
curl -X POST http://localhost:8086/geometry/decode/text \
  -H "Content-Type: application/json" \
  -d '{"constellation_ids": ["urban_farming"], "per_constellation": 5}'
```

### Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `CHIT_REQUIRE_SIGNATURE` | false | Require HMAC on ingest |
| `CHIT_DECRYPT_ANCHORS` | false | Enable anchor decryption |
| `CHIT_PASSPHRASE` | (none) | Secret for signing/decryption |
| `CHIT_CODEBOOK_PATH` | tests/data/codebook.jsonl | Path to codebook |
| `CHIT_LEARNED_TEXT` | false | Use T5 for summarization |
| `CHIT_T5_MODEL` | (none) | HuggingFace model path |

---

## See Also

- [What Is CHIT?](01_WHAT_IS_CHIT.md) — Theory and motivation
- [Geometry Bus](02_GEOMETRY_BUS.md) — NATS integration details
- [EVO SWARM](03_EVO_SWARM.md) — Distributed consensus
- [CHIT Gateway API](CHIT_GATEWAY_API.md) — REST endpoint reference
- [CHIT Implementation Audit](CHIT_IMPLEMENTATION_AUDIT_2026-02-08.md) — Current status

---

*Last updated: 2026-05-20 | Codebase validated against pmoves/*

---

## Appendix: Validation Evidence

### Source File Cross-Reference

| Section | Source File | Key Findings |
|---------|-------------|-------------|
| CGP Structure | `pmoves/services/gateway/gateway/api/chit.py` | Pydantic models: `Point`, `Constellation`, `SuperNode`, `CGP` — matches doc |
| Encoding Flow | `pmoves/tools/chit_backend.py` | CGP v1 generation from JSONL chunks; K=3 default, spectrum histogram |
| Terminal Viz | `pmoves/tools/chit_terminal_viz.py` | Sparklines, bar charts, Poincaré disk, constellation maps — all implemented |
| Security | `pmoves/tools/chit_security.py` | HMAC-SHA256 signing, AES-GCM anchor encryption, PBKDF2 600k iterations |
| Security | `pmoves/tools/chit_common.py` | Canonical JSON for deterministic hashing |
| Graph Signer | `pmoves/services/graph-linker/chit_signer.py` | Additive signing, gated by `CHIT_SIGN_NEO4J` env var |
| ShapeStore | `pmoves/services/common/shape_store.py` | LRU cache, cross-modal jumps, Supabase warm, `geometry.cgp.v1` + `chit.cgp.v0.2` support |
| Frontend | `pmoves/ui/lib/chit.ts` | CHIT manifest loading, target env file parsing |

### API Endpoint Validation

```python
# From chit.py — confirmed endpoints:
POST /geometry/event      → accepts CGP, stores in ShapeStore, syncs Supabase, emits NATS
GET  /shape/point/{pid}/jump → returns modality + ref_id for video/audio/text
POST /geometry/decode/text  → projects codebook onto anchors, matches spectrum
POST /geometry/calibration/report → KL/JS divergence, coverage metrics
```

### Environment Variables

| Variable | Default | Purpose | Source |
|----------|---------|---------|--------|
| `CHIT_REQUIRE_SIGNATURE` | false | Require HMAC on ingest | chit.py:19 |
| `CHIT_DECRYPT_ANCHORS` | false | Enable anchor decryption | chit.py:20 |
| `CHIT_PASSPHRASE` | (none) | Legacy signing/encryption key | chit.py:21 |
| `CHIT_SIGNING_KEY` | (none) | Separate signing key | chit_security.py:40 |
| `CHIT_ENCRYPTION_KEY` | (none) | Separate encryption key | chit_security.py:61 |
| `CHIT_CODEBOOK_PATH` | tests/data/codebook.jsonl | Codebook location | chit.py:31 |
| `CHIT_SIGN_NEO4J` | false | Gate graph signing | chit_signer.py:21 |

---

## Bonus: Remotion + Pretext in PMOVES.AI

### The Remotion Rendering Skill

The `remotion-render` skill bridges A2UI animation specs to video output:

**Skill manifest:** `pmoves/skills/remotion-render/manifest.yaml`

```yaml
name: remotion-render
version: "1.0.0"
description: "Render A2UI animation specs into MP4/GIF/WebM via the Remotion renderer service"

# Input: A2UI animation JSON spec
input:
  required: [a2ui_spec]
  properties:
    a2ui_spec:
      type: object
      # Text elements may opt into text_layout.engine=pretext
    format:
      enum: [mp4, gif, webm]
      default: mp4
    quality:
      enum: [draft, standard, high]
      default: standard

# Output
output:
  url: "MinIO presigned URL"
  duration_ms: integer
  scenes: integer
  layout_summary:
    text_elements: number
    pretext_elements: number  # ← Pretext engine count
    engines: string[]          # ["browser", "pretext"]

# Service
service:
  url: "http://localhost:8105/render"
  alternates:
    - "http://localhost:8105/render/provenance"  # Direct living-doc renders

agent: creator
theme: megaman/dr-wily
```

### A2UI Renderer Service

From `pmoves/services/a2ui-renderer/src/index.ts`:

**Port:** 8105 | **Health:** `/healthz` | **Auth:** JWT (fail-closed)

```typescript
// Remotion imports
import { bundle } from '@remotion/bundler';
import { renderMedia, selectComposition } from '@remotion/renderer';

// Render endpoint
app.post('/render', requireAuth, async (req, res) => {
  const { a2ui_spec, format = 'mp4', quality = 'standard' } = req.body;
  
  // Bundle Remotion composition
  const bundleLocation = await ensureBundle();
  
  // Render to output
  const outputLocation = await renderMedia({
    composition: await selectComposition({ serveUrl: bundleLocation, id: 'A2UIComposition' }),
    codec: format === 'gif' ? 'gif' : 'h264',
    outputLocation,
  });
  
  // Upload to MinIO
  await s3.send(new PutObjectCommand({
    Bucket: MINIO_BUCKET,
    Key: `outputs/${jobId}.${format}`,
    Body: fs.createReadStream(outputLocation),
  }));
  
  // Emit NATS event
  publishNats('a2ui.render.completed.v1', {
    job_id: jobId,
    url: presignedUrl,
    format,
    duration_ms,
  });
  
  res.json({ ok: true, url: presignedUrl });
});

// Provenance living-doc route (direct, no scene builder)
app.post('/render/provenance', requireAuth, async (req, res) => {
  // Renders ProvenanceLivingDoc composition directly
  // Accepts: title, summary, merkle_root, shape_id, weighted_terms, sections
});
```

### Pretext Text Layout Engine

Pretext provides **deterministic, canvas-accurate** text layout for captions, overlays, and living docs:

**Source:** `pmoves/services/a2ui-renderer/src/remotion/pretextLayout.ts`

```typescript
import {
  layoutWithLines,
  measureLineStats,
  measureNaturalWidth,
  prepareWithSegments,
  setLocale,
} from '@chenglou/pretext';

// Layout config options
interface TextLayoutConfig {
  engine?: 'browser' | 'pretext';  // ← opt into Pretext
  maxWidth?: number | string;       // e.g., 720 or "80%"
  lineHeight?: number;
  letterSpacing?: number;
  whiteSpace?: 'normal' | 'pre-wrap';
  wordBreak?: 'normal' | 'keep-all';
  textAlign?: 'left' | 'center' | 'right';
  maxLines?: number;
  shrinkWrap?: boolean;               // ← fit to content width
  debugBoxes?: boolean;              // ← visualize bounding boxes
  locale?: string;
}

// Usage in A2UI spec
{
  "type": "text",
  "content": "Provenance: CHIT-encoded, HMAC-signed, Neo4j-attested",
  "size": { "width": 720 },
  "text_layout": {
    "engine": "pretext",             // ← Pretext engine
    "maxWidth": 720,
    "lineHeight": 1.4,
    "maxLines": 2,
    "shrinkWrap": true,
    "debugBoxes": false
  }
}
```

### Layout Summary Tracking

The renderer tracks Pretext usage for diagnostics:

```typescript
type LayoutSummary = {
  text_elements: number;       // Total text/heading elements
  pretext_elements: number;    // Elements using Pretext engine
  debug_layout_elements: number;
  bounded_text_elements: number;
  engines: string[];           // ["browser", "pretext"]
};

function summarizeLayoutUsage(spec: any): LayoutSummary {
  for (const scene of spec.scenes) {
    for (const element of scene.elements) {
      if (element.type === 'text' || element.type === 'heading') {
        const engine = element.text_layout?.engine ?? 'browser';
        if (engine === 'pretext') {
          pretextElements++;
        }
        engines.add(engine);
      }
    }
  }
  return { text_elements, pretext_elements, engines: [...engines] };
}
```

### Pretext vs Browser Engine

| Feature | Browser Engine | Pretext Engine |
|---------|----------------|----------------|
| Multiline wrap | CSS-based | Canvas-accurate, deterministic |
| Max lines | Approximate | Exact via `maxLines` |
| ShrinkWrap | No | Yes — fit to content |
| Debug boxes | No | Yes — `debugBoxes: true` |
| Fallback | N/A | Returns `null` if no canvas |
| CJK support | Variable | Via `locale` parameter |

**Fallback behavior:** When `OffscreenCanvas` / `document` is unavailable, Pretext returns `null` and the renderer falls back to normal browser text wrapping — **never fails closed**.

### Pretext Package Surface

```
@chenglou/pretext
├── layoutWithLines(text, maxWidth, lineHeight)
├── measureLineStats(prepared, maxWidth)
├── measureNaturalWidth(prepared)
├── prepareWithSegments(text, font, options)
└── setLocale(locale)
```

**PMOVES fork:** `POWERFULMOVES/Pmoves-pretext` for living-doc alignment

### Quick Commands

```bash
# Render a chart via A2UI → Remotion
curl -X POST http://localhost:8105/render \
  -H "Authorization: Bearer $JWT" \
  -d '{"a2ui_spec": {...}, "format": "mp4", "quality": "high"}'

# Render provenance living doc directly
curl -X POST http://localhost:8105/render/provenance \
  -H "Authorization: Bearer $JWT" \
  -d '{"title": "...", "sections": [...], "merkle_root": "..."}'

# Local: render a still preview
cd pmoves/services/a2ui-renderer
npm run render:provenance:still

# Video export
npm run render:provenance:file -- demos/provenance_living_doc.mof_example.json output.mp4
```

### NATS Events

| Subject | Payload |
|---------|---------|
| `a2ui.render.started.v1` | job_id, spec_hash, format |
| `a2ui.render.completed.v1` | job_id, url, duration_ms, layout_summary |
| `skills.pipeline.model-benchmark-viz.v1` | Chart spec → Remotion render |
| `skills.pipeline.research-render.v1` | Research summary → Remotion render |