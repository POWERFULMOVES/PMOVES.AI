# CHIT Gateway API Reference

**Version:** 2026-02-18 | **Spec:** `chit.cgp.v0.2` | **Service:** `gateway` (port 8000)

---

## Overview

The CHIT Gateway is the HTTP interface for the Cymatic Holographic Information Theory (CHIT) system within PMOVES.AI. It provides endpoints to:

- **Publish** CGP (Constellation Geometry Packet) events into the ShapeStore and Supabase
- **Decode** constellation spectra against a codebook to recover text
- **Calibrate** how well a codebook reconstructs a constellation's spectrum
- **Jump** across modalities (video/audio/text) via point references
- **Visualize** constellations as SVG polar plots

### Quick Start (3 Steps)

```bash
# 1. Publish a CGP
curl -X POST http://localhost:8000/geometry/event \
  -H "Content-Type: application/json" \
  -d '{"type": "geometry.cgp.v1", "data": <CGP_JSON>}'

# 2. Decode text from constellations
curl -X POST http://localhost:8000/geometry/decode/text \
  -H "Content-Type: application/json" \
  -d '{"shape_id": "<SHAPE_ID>", "constellation_ids": ["const-1"]}'

# 3. Get a cross-modal jump locator
curl http://localhost:8000/shape/point/pt-1/jump
```

---

## Concepts for Students

### What is CGP?

A **Constellation Geometry Packet** (CGP) is a JSON document that encodes multimodal content (text, video, audio) as geometric structures. Think of it as a "fingerprint" for a piece of content where:

- **Super Nodes** group related content clusters
- **Constellations** are individual topic clusters, each with an **anchor** vector (direction in embedding space), a **spectrum** (energy distribution across radial bins), and **radial_minmax** (the range of projections)
- **Points** are individual data references (a video timestamp, a text span, an audio segment)

### Key Vocabulary

| Term | Meaning |
|------|---------|
| `shape_id` | SHA-256 hash (first 16 hex chars) of the canonical CGP, used as a unique identifier |
| `constellation` | A topic cluster with an anchor direction, spectrum, and associated points |
| `anchor` | A unit vector in embedding space that defines the constellation's "direction" |
| `spectrum` | A probability distribution over radial bins; describes how content energy is distributed |
| `codebook` | A JSONL file of `{"text": "...", "vec": [...]}` entries used to decode spectra back to text |
| `cross-modal jump` | Looking up a point ID to get a locator in another modality (e.g., point -> video timestamp) |
| `radial_minmax` | The `[min, max]` range of scalar projections onto the anchor vector |

### Security Model

The gateway supports two optional security layers:

1. **HMAC-SHA256 signatures** (`CHIT_REQUIRE_SIGNATURE=true`): The CGP (minus the `sig` field) is canonicalized (sorted keys, compact JSON), then HMAC'd with the shared passphrase. Requests with invalid signatures are rejected with 400.
2. **AES-GCM anchor encryption** (`CHIT_DECRYPT_ANCHORS=true`): Anchor vectors can be encrypted at rest. The gateway derives a key via scrypt from the passphrase and decrypts on ingestion.

---

## Pydantic Models

### Point

```python
class Point(BaseModel):
    id: Optional[str] = None
    x: Optional[float] = None
    y: Optional[float] = None
    proj: Optional[float] = None
    conf: Optional[float] = None
    text: Optional[str] = None
    source_ref: Optional[str] = None
```

### Constellation

```python
class Constellation(BaseModel):
    id: str
    anchor: Optional[List[float]] = None
    anchor_enc: Optional[Dict[str, Any]] = None    # AES-GCM encrypted anchor
    summary: Optional[str] = None
    radial_minmax: List[float]                      # [min, max]
    spectrum: List[float]                            # probability distribution
    points: List[Point] = []
```

### SuperNode

```python
class SuperNode(BaseModel):
    id: str
    constellations: List[Constellation]
```

### CGP

```python
class CGP(BaseModel):
    spec: str                          # e.g. "chit.cgp.v0.2"
    meta: Dict[str, Any]
    super_nodes: List[SuperNode]
    sig: Optional[Dict[str, Any]] = None  # HMAC signature block
```

### GeometryEventEnvelope

Wrapper for the `/geometry/event` endpoint:

```python
class GeometryEventEnvelope(BaseModel):
    type: str    # "geometry.cgp.v1" or "chit.cgp.v0.2"
    data: CGP
```

### GeometryDecodeTextRequest

Request body for `/geometry/decode/text`:

```python
class GeometryDecodeTextRequest(BaseModel):
    shape_id: Optional[str] = None
    constellation_ids: List[str] = []
    per_constellation: int = 10
    codebook_path: Optional[str] = None     # filename only (sandboxed)
    sig: Optional[Dict[str, Any]] = None    # required if codebook_path + CHIT_REQUIRE_SIGNATURE
```

### GeometryCalibrationRequest

Request body for `/geometry/calibration/report`:

```python
class GeometryCalibrationRequest(BaseModel):
    cgp: CGP
    codebook_path: Optional[str] = None     # filename only (sandboxed)
    sig: Optional[Dict[str, Any]] = None    # required if codebook_path + CHIT_REQUIRE_SIGNATURE
```

---

## Endpoints

### POST /geometry/event

Ingest a CGP packet into the ShapeStore and optionally sync to Supabase.

**Request body:** `GeometryEventEnvelope`

```json
{
  "type": "geometry.cgp.v1",
  "data": {
    "spec": "chit.cgp.v0.2",
    "meta": {},
    "super_nodes": [
      {
        "id": "sn-1",
        "constellations": [
          {
            "id": "const-1",
            "anchor": [1.0, 0.0, 0.0],
            "summary": "demo constellation",
            "radial_minmax": [0.0, 1.0],
            "spectrum": [0.3, 0.4, 0.3],
            "points": [
              {
                "id": "pt-1",
                "modality": "video",
                "ref_id": "yt123",
                "t_start": 12.5
              }
            ]
          }
        ]
      }
    ]
  }
}
```

**Success response (200):**

```json
{
  "ok": true,
  "shape_id": "a1b2c3d4e5f67890",
  "event": "geometry.cgp.v1"
}
```

**Error codes:**

| Code | Condition |
|------|-----------|
| 400 | Unsupported event type (not `geometry.cgp.v1` or `chit.cgp.v0.2`) |
| 400 | Invalid/missing HMAC when `CHIT_REQUIRE_SIGNATURE=true` |
| 400 | Encrypted anchor but `CHIT_DECRYPT_ANCHORS=false` |
| 502 | Supabase sync failure |
| 503 | ShapeStore unavailable (not initialized) |

**Processing pipeline (9 steps):**

1. Validate envelope type is in accepted set (`geometry.cgp.v1`, `chit.cgp.v0.2`)
2. If `CHIT_REQUIRE_SIGNATURE=true`, verify HMAC-SHA256 over canonical CGP
3. For each constellation, if `anchor_enc` present and `CHIT_DECRYPT_ANCHORS=true`, derive key via scrypt and decrypt with AES-GCM
4. Compute `shape_id` = first 16 hex chars of SHA-256 of canonical CGP (sans `sig`)
5. Auto-assign point IDs for any points missing `id` (format: `p:<shape_id>:<index>`)
6. Copy `source_ref` to `ref_id` if `ref_id` missing
7. Record constellation IDs in the shape-to-constellations index
8. Call `shape_store.on_geometry_event()` to ingest into in-memory LRU cache
9. Persist CGP to `data/<shape_id>.json` and sync to Supabase (if configured)

**curl example:**

```bash
curl -X POST http://localhost:8000/geometry/event \
  -H "Content-Type: application/json" \
  -d '{
    "type": "geometry.cgp.v1",
    "data": {
      "spec": "chit.cgp.v0.2",
      "meta": {},
      "super_nodes": [{
        "id": "sn-1",
        "constellations": [{
          "id": "const-1",
          "anchor": [1.0, 0.0, 0.0],
          "summary": "test",
          "radial_minmax": [0.0, 1.0],
          "spectrum": [0.5, 0.5],
          "points": []
        }]
      }]
    }
  }'
```

**Python example:**

```python
import requests

envelope = {
    "type": "geometry.cgp.v1",
    "data": {
        "spec": "chit.cgp.v0.2",
        "meta": {},
        "super_nodes": [{
            "id": "sn-1",
            "constellations": [{
                "id": "const-1",
                "anchor": [1.0, 0.0, 0.0],
                "summary": "test",
                "radial_minmax": [0.0, 1.0],
                "spectrum": [0.5, 0.5],
                "points": []
            }]
        }]
    }
}
resp = requests.post("http://localhost:8000/geometry/event", json=envelope)
print(resp.json())  # {"ok": true, "shape_id": "...", "event": "geometry.cgp.v1"}
```

**JavaScript example:**

```javascript
const resp = await fetch("http://localhost:8000/geometry/event", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    type: "geometry.cgp.v1",
    data: {
      spec: "chit.cgp.v0.2",
      meta: {},
      super_nodes: [{
        id: "sn-1",
        constellations: [{
          id: "const-1",
          anchor: [1.0, 0.0, 0.0],
          summary: "test",
          radial_minmax: [0.0, 1.0],
          spectrum: [0.5, 0.5],
          points: []
        }]
      }]
    }
  })
});
const data = await resp.json();
console.log(data); // {ok: true, shape_id: "...", event: "geometry.cgp.v1"}
```

---

### GET /shape/point/{pid}/jump

Return a cross-modal locator for a point, enabling UI/agents to jump to the underlying data.

**Path parameter:** `pid` - The point ID (e.g., `pt-1`, `p:a1b2c3d4:0`)

**Success response (200):**

```json
{
  "ok": true,
  "locator": {
    "modality": "video",
    "ref_id": "yt123",
    "t": 12.5,
    "frame": 750
  }
}
```

**Locator formats by modality:**

| Modality | Fields |
|----------|--------|
| `video` | `modality`, `ref_id`, `t` (seconds), `frame` (index) |
| `audio` | `modality`, `ref_id`, `t` (seconds) |
| `text` | `modality`, `ref_id`, `token_start`, `token_end` |

**Fallback for `v:` prefix:** If the point is not found in the store but the ID starts with `v:` and contains `#t=`, the endpoint parses it as a video locator directly. For example, `v:yt123#t=31.25-45.0` returns:

```json
{
  "ok": true,
  "locator": { "modality": "video", "ref_id": "yt123", "t": 31.25 }
}
```

**Error codes:**

| Code | Condition |
|------|-----------|
| 404 | Point not found (and no `v:` fallback match) |
| 503 | ShapeStore unavailable |

**curl example:**

```bash
curl http://localhost:8000/shape/point/pt-1/jump
```

---

### POST /geometry/decode/text

Decode constellation spectra against a codebook to recover ranked text items.

**Request body:** `GeometryDecodeTextRequest`

```json
{
  "shape_id": "a1b2c3d4e5f67890",
  "constellation_ids": ["const-1"],
  "per_constellation": 10,
  "codebook_path": null
}
```

**Success response (200):**

```json
{
  "items": [
    {
      "constellation_id": "const-1",
      "text": "decoded text entry",
      "proj_est": 0.82,
      "score": 0.35
    }
  ]
}
```

If `CHIT_LEARNED_TEXT=true`, the response includes an additional `learned` field:

```json
{
  "items": [...],
  "learned": {
    "mode": "transformers",
    "summary": "A brief model-generated summary"
  }
}
```

Or with keyword fallback:

```json
{
  "items": [...],
  "learned": {
    "mode": "freq",
    "keywords": "word1, word2, word3"
  }
}
```

**Decoding algorithm (6 steps):**

1. Resolve constellation IDs from `shape_id` (via shape-to-constellations index) and/or `constellation_ids`
2. For each constellation, obtain the anchor vector (decrypt if encrypted)
3. Normalize the anchor to a unit vector `u`
4. For each codebook entry with a `vec` field, compute the scalar projection `proj = dot(u, vec)`
5. Map each projection to the nearest spectrum bin center, look up the spectrum weight
6. Sort by spectrum weight descending, return top `per_constellation` items

**Learned text modes:** When `CHIT_LEARNED_TEXT=true`:
- If `CHIT_T5_MODEL` is set and `transformers` is installed, a T5/summarization pipeline generates a summary of the top decoded texts
- Otherwise, a frequency-based keyword extractor produces the top 8 keywords

**Codebook format:** JSONL where each line is:

```json
{"text": "some phrase or sentence", "vec": [0.1, -0.3, 0.5, ...]}
```

**Error codes:**

| Code | Condition |
|------|-----------|
| 400 | Neither `constellation_ids` nor `shape_id` provided |
| 403 | `codebook_path` provided but HMAC signature missing/invalid (when `CHIT_REQUIRE_SIGNATURE=true`) |
| 404 | No constellations found for the given IDs |
| 503 | ShapeStore unavailable |

**curl example:**

```bash
curl -X POST http://localhost:8000/geometry/decode/text \
  -H "Content-Type: application/json" \
  -d '{
    "shape_id": "a1b2c3d4e5f67890",
    "constellation_ids": ["const-1"],
    "per_constellation": 5
  }'
```

**Python example:**

```python
resp = requests.post("http://localhost:8000/geometry/decode/text", json={
    "shape_id": "a1b2c3d4e5f67890",
    "constellation_ids": ["const-1"],
    "per_constellation": 5,
})
for item in resp.json()["items"]:
    print(f"{item['score']:.3f}  {item['text']}")
```

---

### POST /geometry/calibration/report

Measure how well a codebook reconstructs a constellation's spectrum using KL and Jensen-Shannon divergence.

**Request body:** `GeometryCalibrationRequest`

```json
{
  "cgp": {
    "spec": "chit.cgp.v0.2",
    "meta": {},
    "super_nodes": [{
      "id": "sn-1",
      "constellations": [{
        "id": "const-1",
        "anchor": [1.0, 0.0, 0.0],
        "summary": "test",
        "radial_minmax": [0.0, 1.0],
        "spectrum": [0.3, 0.4, 0.3],
        "points": []
      }]
    }]
  },
  "codebook_path": null
}
```

> **Important:** The endpoint uses only the **first constellation** of the **first super node** (`cgp.super_nodes[0].constellations[0]`). Additional constellations are ignored.

**Success response (200):**

```json
{
  "KL": 0.0523,
  "JS": 0.0131,
  "coverage": 0.67,
  "report": "artifacts/reconstruction_report.md"
}
```

**Algorithm:**

1. Load codebook entries from the specified (or default) path
2. Extract the first constellation's anchor; normalize to unit vector `u`
3. Project every codebook vector onto `u` to get scalar values
4. Bin the projections into a histogram matching the constellation's `radial_minmax` and `spectrum` size
5. Normalize the histogram to get the empirical distribution
6. Compute `KL(target || empirical)` and `JS(target, empirical)` divergence
7. Compute coverage = fraction of bins with at least one codebook hit
8. Write a Markdown report to `artifacts/reconstruction_report.md`

**Error codes:**

| Code | Condition |
|------|-----------|
| 400 | No anchor available (neither plaintext nor decryptable) |
| 403 | `codebook_path` provided but HMAC signature invalid (when `CHIT_REQUIRE_SIGNATURE=true`) |

**curl example:**

```bash
curl -X POST http://localhost:8000/geometry/calibration/report \
  -H "Content-Type: application/json" \
  -d '{
    "cgp": {
      "spec": "chit.cgp.v0.2",
      "meta": {},
      "super_nodes": [{
        "id": "sn-1",
        "constellations": [{
          "id": "const-1",
          "anchor": [1.0, 0.0, 0.0],
          "summary": "test",
          "radial_minmax": [0.0, 1.0],
          "spectrum": [0.3, 0.4, 0.3],
          "points": []
        }]
      }]
    }
  }'
```

---

## Visualization Endpoints

All visualization routes are under the `/viz` prefix.

| Method | Route | Description |
|--------|-------|-------------|
| POST | `/viz/constellation.svg` | Render a single constellation as an SVG polar plot. Query params: `dim_x`, `dim_y` (anchor dims), `rotate` (degrees) |
| GET | `/viz/shape/{shape_id}.svg` | Render a saved shape's constellation. Query params: `super_idx`, `const_idx`, `dim_x`, `dim_y`, `rotate` |
| POST | `/viz/preview/decode` | Decode a constellation against the codebook without saving. Query param: `per_constellation`, `codebook_path` |
| POST | `/viz/mix/decode` | Interpolate two constellations (anchor + spectrum) and decode. Body: `{const_a, const_b, alpha_anchor, alpha_spectrum}` |
| GET | `/viz/recent` | List recently saved shape IDs (default limit: 10) |
| GET | `/viz/shape/{shape_id}/constellations` | List constellations within a saved shape |
| POST | `/viz/preview/calibration` | Run calibration on a single constellation without the full `GeometryCalibrationRequest` wrapper |
| POST | `/viz/mix/calibration` | Interpolate two constellations and run calibration. Body: `{const_a, const_b, alpha_anchor, alpha_spectrum}` |

**SVG output:** Constellation SVGs render as polar plots with:
- Radial grid lines and 8 angular guide lines
- Colored spectrum bars radiating from center (hue varies by bin index)
- Cyan anchor direction arrow
- Axis dimension labels

**Example: Render a shape SVG**

```bash
curl "http://localhost:8000/viz/shape/a1b2c3d4e5f67890.svg?dim_x=0&dim_y=1&rotate=45"
```

**Example: Mix and decode two constellations**

```bash
curl -X POST "http://localhost:8000/viz/mix/decode?per_constellation=10" \
  -H "Content-Type: application/json" \
  -d '{
    "const_a": {"id": "c1", "anchor": [1,0,0], "radial_minmax": [0,1], "spectrum": [0.5,0.5]},
    "const_b": {"id": "c2", "anchor": [0,1,0], "radial_minmax": [0,1], "spectrum": [0.3,0.7]},
    "alpha_anchor": 0.5,
    "alpha_spectrum": 0.5
  }'
```

---

## ShapeStore Reference

**Source:** `pmoves/services/common/shape_store.py`

The ShapeStore is an in-memory LRU cache that powers sub-100ms cross-modal lookups.

### Architecture

- **LRU capacity:** 10,000 entries (configurable via constructor)
- **Thread safety:** `threading.RLock` for all read/write operations
- **Storage maps:**
  - `_anchors` - anchor vectors keyed by ID
  - `_constellations` - full constellation dicts keyed by constellation ID
  - `_points` - `ShapePoint` dataclass instances keyed by point ID
  - `_lru` - `OrderedDict` tracking access order for eviction
  - `_pack_meta` - builder pack metadata keyed by `(namespace, modality)`

### ShapePoint Dataclass

```python
@dataclass
class ShapePoint:
    id: str
    constellation_id: str
    modality: str              # "video", "audio", "text"
    ref_id: str                # video ID, doc ID, etc.
    t_start: Optional[float]   # start time (video/audio)
    t_end: Optional[float]     # end time
    frame_idx: Optional[int]   # frame index (video)
    token_start: Optional[int] # token offset (text)
    token_end: Optional[int]   # token end offset (text)
    proj: Optional[float]      # scalar projection value
    conf: Optional[float]      # confidence score
    meta: Dict[str, Any]       # additional metadata
```

### Key Methods

| Method | Description |
|--------|-------------|
| `put_cgp(cgp)` | Ingest a CGP dict; indexes constellations and points |
| `get_constellation(cid)` | Retrieve a constellation by ID (touches LRU) |
| `get_point(pid)` | Retrieve a ShapePoint by ID (touches LRU) |
| `jump_locator(pid)` | Return a compact locator dict for cross-modal jumps |
| `on_geometry_event(event)` | Handle bus messages; validates type then calls `put_cgp` |
| `warm_from_db(...)` | Async: load recent CGPs from Supabase PostgREST |
| `update_builder_pack(ns, mod, pack)` | Set builder pack metadata for a namespace/modality |
| `get_builder_pack(ns, mod)` | Retrieve builder pack metadata |

### warm_from_db() Supabase Loading

The `warm_from_db` method fetches recent CGPs from Supabase using three table strategies (tried in order until one succeeds):

1. `geometry_cgp_packets` - Raw CGP payloads
2. `geometry_cgp_v1` - Legacy v1 format payloads
3. `constellations` - Normalized table with joined `anchors` and `shape_points`

Environment variables used:
- `SUPA_REST_URL` or `SUPABASE_REST_URL` - PostgREST base URL
- `SUPABASE_SERVICE_ROLE_KEY` / `SUPABASE_SERVICE_KEY` / `SUPABASE_KEY` / `SUPABASE_ANON_KEY` - API key

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `CHIT_REQUIRE_SIGNATURE` | `"false"` | When `"true"`, reject CGPs without valid HMAC-SHA256 |
| `CHIT_DECRYPT_ANCHORS` | `"false"` | When `"true"`, decrypt AES-GCM encrypted anchors |
| `CHIT_PASSPHRASE` | `"change-me"` | Shared secret for HMAC signing and scrypt key derivation |
| `CHIT_CODEBOOK_PATH` | `"tests/data/codebook.jsonl"` | Default codebook file path (directory used for sandboxing) |
| `CHIT_LEARNED_TEXT` | `"false"` | When `"true"`, enhance decode results with learned summaries |
| `CHIT_T5_MODEL` | `None` | HuggingFace model name/path for T5 summarization (optional) |
| `SUPA_REST_URL` | `None` | Supabase PostgREST URL for ShapeStore warm loading |
| `SUPABASE_REST_URL` | `None` | Alternative env var for PostgREST URL |
| `SUPABASE_SERVICE_ROLE_KEY` | `None` | Supabase service role API key |
| `SUPABASE_SERVICE_KEY` | `None` | Alternative Supabase API key |
| `SUPABASE_ANON_KEY` | `None` | Supabase anon key (fallback) |

---

## Security Configuration Guide

### HMAC Signature Setup

1. Set a strong passphrase:
   ```bash
   export CHIT_PASSPHRASE="your-strong-random-passphrase"
   export CHIT_REQUIRE_SIGNATURE=true
   ```

2. Sign CGPs before publishing using the CLI tool:
   ```bash
   python scripts/chit_sign.py \
     --in cgp.json --out cgp_signed.json \
     --passphrase "your-strong-random-passphrase"
   ```

3. The signature is a JSON block appended as `sig` to the CGP:
   ```json
   {
     "sig": {
       "alg": "HMAC-SHA256",
       "kid": "demo",
       "ts": 1708300000,
       "hmac": "<base64-encoded-digest>"
     }
   }
   ```

### Anchor Encryption Setup

1. Enable decryption on the gateway:
   ```bash
   export CHIT_DECRYPT_ANCHORS=true
   export CHIT_PASSPHRASE="your-strong-random-passphrase"
   ```

2. Encrypt anchors in CGPs:
   ```bash
   python scripts/chit_sign.py \
     --in cgp.json --out cgp_encrypted.json \
     --passphrase "your-strong-random-passphrase" \
     --encrypt-anchors
   ```

3. Encrypted anchors replace the `anchor` field with `anchor_enc`:
   ```json
   {
     "anchor_enc": {
       "iv": "<base64>",
       "salt": "<base64>",
       "ct": "<base64>"
     }
   }
   ```

### Codebook Path Sandboxing

When `codebook_path` is provided in decode/calibration requests, only the **basename** is used. The file is resolved relative to the directory of `CHIT_CODEBOOK_PATH`. This prevents path traversal attacks.

Example: If `CHIT_CODEBOOK_PATH=tests/data/codebook.jsonl` and a request sends `codebook_path="../../../etc/passwd"`, the resolved path is `tests/data/passwd` (basename extraction).

### Production Hardening Checklist

- [ ] Set `CHIT_REQUIRE_SIGNATURE=true`
- [ ] Set `CHIT_PASSPHRASE` to a strong random value (not `change-me`)
- [ ] Set `CHIT_DECRYPT_ANCHORS=true` if using encrypted anchors
- [ ] Set `CHIT_CODEBOOK_PATH` to a production codebook directory
- [ ] Restrict network access to the gateway port
- [ ] Enable Supabase sync for persistence beyond in-memory cache
- [ ] Monitor `/metrics` endpoint via Prometheus

---

## Web Client Usage Guide

**Access:** `http://localhost:8000/web/client.html`

### UI Elements

- **Server base** input - Target gateway URL (default: `http://localhost:8000`)
- **CGP textarea** - Paste CGP JSON here
- **Sign checkbox** - Request HMAC signing (note: browser-side signing not implemented; use `chit_sign.py`)
- **Encrypt checkbox** - Request anchor encryption (same limitation)
- **Passphrase input** - Shared secret (default: `change-me`)
- **Publish button** - POST to `/geometry/event`
- **Decode button** - POST to `/geometry/decode/text`
- **Calibration button** - POST to `/geometry/calibration/report`
- **Result pane** - Shows JSON response
- **Links bar** - After publish, shows links to Shape SVG, Raw JSON, and Decode views

### 5-Step Walkthrough

1. Open `http://localhost:8000/web/client.html` in a browser
2. Paste a CGP JSON (try the fixture from `tests/data/cgp_fixture.json`)
3. Click **Publish** to send to `/geometry/event`
4. Click **Decode** to retrieve text items from the published constellations
5. Click **Calibration** to measure codebook reconstruction quality

### XSS Protection

The `safeBase()` function validates the server URL input. Only `http:` and `https:` protocols are allowed. Relative paths starting with `/` are also accepted. Any other input falls back to `http://localhost:8000`. This prevents `javascript:` URI injection.

### Signing Limitation

Browser-side HMAC signing is not implemented in the web client. When the Sign or Encrypt checkboxes are checked, an alert notifies the user to use `scripts/chit_sign.py` instead. The gateway still accepts unsigned CGPs when `CHIT_REQUIRE_SIGNATURE=false` (the default).

---

## CLI Tools

### chit_sign.py

Sign and optionally encrypt CGP packets.

**Location:** `pmoves/services/gateway/scripts/chit_sign.py`

```bash
python scripts/chit_sign.py \
  --in tests/data/cgp_fixture.json \
  --out data/cgp_signed.json \
  --passphrase "secret" \
  --encrypt-anchors
```

| Flag | Description |
|------|-------------|
| `--in` | Input CGP JSON file (required) |
| `--out` | Output file path (required) |
| `--passphrase` | HMAC-SHA256 passphrase; also used for scrypt key derivation |
| `--encrypt-anchors` | Replace `anchor` fields with AES-GCM `anchor_enc` blocks |

### chit_client.py

End-to-end smoke test client that runs publish, decode, and calibration.

**Location:** `pmoves/services/gateway/scripts/chit_client.py`

```bash
python scripts/chit_client.py \
  --base http://localhost:8000 \
  --cgp tests/data/cgp_fixture.json \
  --sign "secret" \
  --encrypt-anchors \
  --per-constellation 5
```

| Flag | Description |
|------|-------------|
| `--base` | Gateway base URL (default: `http://localhost:8000`) |
| `--cgp` | CGP fixture file (default: `tests/data/cgp_fixture.json`) |
| `--sign` | Passphrase for signing (optional) |
| `--encrypt-anchors` | Encrypt anchors before publishing |
| `--per-constellation` | Max decoded items per constellation (default: 5) |

**Steps performed:**
1. Optionally sign/encrypt the CGP
2. POST to `/geometry/event`
3. POST to `/geometry/decode/text` with all constellation IDs
4. POST to `/geometry/calibration/report`

### mini_geometry_decode.py

Standalone calibration script (no server required).

**Location:** `pmoves/services/gateway/scripts/mini_geometry_decode.py`

```bash
python scripts/mini_geometry_decode.py \
  --cgp tests/data/cgp_fixture.json \
  --codebook tests/data/codebook.jsonl \
  --out-json tests/artifacts/metrics.json \
  --out-md tests/artifacts/metrics.md
```

| Flag | Description |
|------|-------------|
| `--cgp` | CGP fixture file (default: `tests/data/cgp_fixture.json`) |
| `--codebook` | Codebook JSONL file (default: `tests/data/codebook.jsonl`) |
| `--out-json` | Output metrics JSON (default: `tests/artifacts/metrics.json`) |
| `--out-md` | Output Markdown report (default: `tests/artifacts/metrics.md`) |

---

## Supabase Tables

The gateway syncs CGP data to three Supabase tables (when configured):

### anchors

| Column | Type | Description |
|--------|------|-------------|
| `id` | text (PK) | Constellation ID |
| `anchor` | jsonb | Anchor vector array |
| `created_at` | timestamptz | Insertion timestamp |

### constellations

| Column | Type | Description |
|--------|------|-------------|
| `id` | text (PK) | Constellation ID |
| `summary` | text | Human-readable summary |
| `spectrum` | jsonb | Spectrum probability distribution |
| `radial_min` | float | Min radial projection |
| `radial_max` | float | Max radial projection |
| `meta` | jsonb | Additional metadata |
| `created_at` | timestamptz | Insertion timestamp |

### shape_points

| Column | Type | Description |
|--------|------|-------------|
| `id` | text (PK) | Point ID |
| `constellation_id` | text (FK) | Parent constellation |
| `modality` | text | `video`, `audio`, or `text` |
| `ref_id` | text | Reference ID (video ID, doc ID, etc.) |
| `t_start` | float | Start time |
| `t_end` | float | End time |
| `frame_idx` | int | Frame index (video) |
| `token_start` | int | Token start offset (text) |
| `token_end` | int | Token end offset (text) |
| `proj` | float | Scalar projection |
| `conf` | float | Confidence score |
| `meta` | jsonb | Additional metadata |

---

## Testing

### Test Suite

```bash
# Run all gateway geometry tests
pytest pmoves/services/gateway/tests/test_geometry_endpoints.py -v

# Run calibration fixture tests
pytest pmoves/services/gateway/tests/test_calibration_fixture.py -v
```

### Test Fixtures

| File | Description |
|------|-------------|
| `tests/data/cgp_fixture.json` | Sample CGP packet for integration testing |
| `tests/data/codebook.jsonl` | Sample codebook for decode/calibration tests |

### Key Test Cases

- `test_geometry_event_decode_and_jump` - Full publish/decode/jump round-trip
- `test_geometry_event_supabase_idempotent` - Verifies upsert idempotency with Supabase

---

## Related Documentation

| Document | Description |
|----------|-------------|
| [`PMOVESCHIT.md`](./PMOVESCHIT.md) | Core CHIT specification and CGP v0.1 |
| [`PMOVESCHIT_DECODERv0.1.md`](./PMOVESCHIT_DECODERv0.1.md) | Decoder specification |
| [`PMOVESCHIT_DECODER_MULTIv0.1.md`](./PMOVESCHIT_DECODER_MULTIv0.1.md) | Multi-modal decoder (CLIP/CLAP) |
| [`CGP_v1.0_SPECIFICATION.md`](./CGP_v1.0_SPECIFICATION.md) | Production CGP v1.0 spec |
| [`GEOMETRY_BUS_INTEGRATION.md`](./GEOMETRY_BUS_INTEGRATION.md) | NATS integration guide |
| [`IMPLEMENTATION_STATUS.md`](./IMPLEMENTATION_STATUS.md) | Component implementation tracking |
| [`../../services/gateway/README.md`](../../services/gateway/README.md) | Gateway service README |
