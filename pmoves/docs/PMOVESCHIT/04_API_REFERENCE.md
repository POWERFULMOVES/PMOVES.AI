# CHIT API Reference

Complete reference for the CHIT gateway endpoints. All endpoints are served by the PMOVES Gateway (default: `http://localhost:8086`).

---

## Table of Contents

- [CHIT Endpoints](#chit-endpoints)
  - [POST /geometry/event](#post-geometryevent)
  - [POST /geometry/decode/text](#post-geometrydecodetext)
  - [POST /geometry/calibration/report](#post-geometrycalibrationreport)
  - [GET /shape/point/{pid}/jump](#get-shapepointpidjump)
- [Visualization Endpoints](#visualization-endpoints)
  - [POST /viz/constellation.svg](#post-vizconstellationsvg)
  - [GET /viz/shape/{shape_id}.svg](#get-vizshapeshape_idsvg)
  - [POST /viz/preview/decode](#post-vizpreviewdecode)
  - [POST /viz/mix/decode](#post-vizmixdecode)
  - [POST /viz/preview/calibration](#post-vizpreviewcalibration)
  - [POST /viz/mix/calibration](#post-vizmixcalibration)
  - [GET /viz/recent](#get-vizrecent)
  - [GET /viz/shape/{shape_id}/constellations](#get-vizshapeshape_idconstellations)
- [Workflow Endpoints](#workflow-endpoints)
  - [POST /workflow/demo_run](#post-workflowdemo_run)
- [Environment Variables](#environment-variables)
- [HMAC Signing](#hmac-signing)

---

## CHIT Endpoints

### POST /geometry/event

Ingest a CGP packet into the ShapeStore.

**Request body** (`GeometryEventEnvelope`):

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `type` | string | yes | Event type. Must be `"geometry.cgp.v1"` or `"chit.cgp.v1.0"` |
| `data` | CGP | yes | The CGP packet (see [CGP Schema](CGP_v1.0_SPECIFICATION.md)) |

**Response:**

```json
{"ok": true, "shape_id": "a1b2c3d4e5f67890", "event": "chit.cgp.v1.0"}
```

**Errors:**
- `400` — Unsupported event type, or invalid HMAC when `CHIT_REQUIRE_SIGNATURE=true`
- `502` — Supabase sync failed
- `503` — ShapeStore unavailable

**Example:**

```bash
curl -X POST http://localhost:8086/geometry/event \
  -H "Content-Type: application/json" \
  -d '{
    "type": "chit.cgp.v1.0",
    "data": {
      "spec": "chit.cgp.v1.0",
      "meta": {"source": "text", "units_mode": "sentences", "K": 1, "bins": 4, "backend": "all-MiniLM-L6-v2"},
      "super_nodes": [{
        "id": "s0",
        "constellations": [{
          "id": "c0",
          "anchor": [0.5, 0.5, 0.5],
          "radial_minmax": [0.0, 1.0],
          "spectrum": [0.25, 0.25, 0.25, 0.25]
        }]
      }]
    }
  }'
```

---

### POST /geometry/decode/text

Decode text from stored constellations using a codebook.

**Request body** (`GeometryDecodeTextRequest`):

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `shape_id` | string | no | Shape ID to decode (resolves to constellation IDs) |
| `constellation_ids` | string[] | no | Explicit constellation IDs (merged with shape_id results) |
| `per_constellation` | int | no | Max results per constellation (default: 10) |
| `codebook_path` | string | no | Codebook filename (basename only; resolved against `CHIT_CODEBOOK_PATH` directory) |
| `sig` | object | no | HMAC signature (required when `codebook_path` is set and `CHIT_REQUIRE_SIGNATURE=true`) |

At least one of `shape_id` or `constellation_ids` must be provided.

**Response:**

```json
{
  "items": [
    {
      "constellation_id": "c0",
      "text": "matched codebook entry text",
      "proj_est": 0.73,
      "score": 0.92
    }
  ],
  "missing": ["c_not_found"],
  "learned": {"mode": "freq", "keywords": "word1, word2, ..."}
}
```

The `learned` field only appears when `CHIT_LEARNED_TEXT=true`. The `missing` field only appears when some constellation IDs were not found.

**Errors:**
- `400` — No constellation IDs provided
- `403` — `codebook_path` requires CHIT-signed request
- `404` — No constellations found
- `503` — ShapeStore unavailable

**Example:**

```bash
curl -X POST http://localhost:8086/geometry/decode/text \
  -H "Content-Type: application/json" \
  -d '{
    "shape_id": "a1b2c3d4e5f67890",
    "per_constellation": 5
  }'
```

---

### POST /geometry/calibration/report

Compute calibration metrics (KL divergence, JS divergence, coverage) for a CGP against a codebook.

**Query parameters:**

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `codebook_path` | string | no | Codebook filename (basename only) |
| `sig` | object | no | HMAC signature (required when `codebook_path` is set and `CHIT_REQUIRE_SIGNATURE=true`) |

**Request body:** A `GeometryCalibrationRequest` wrapping a CGP object. The first constellation of the first super node is used for calibration.

**Response:**

```json
{
  "KL": 0.0342,
  "JS": 0.0089,
  "coverage": 0.875,
  "report": "artifacts/reconstruction_report.md"
}
```

Returns `{"KL": null, "JS": null, "coverage": 0.0}` if the codebook is empty or not found.

**Errors:**
- `400` — No anchor available in the constellation
- `403` — `codebook_path` requires CHIT-signed request

**Example:**

```bash
curl -X POST http://localhost:8086/geometry/calibration/report \
  -H "Content-Type: application/json" \
  -d '{
    "cgp": {
      "spec": "chit.cgp.v1.0",
      "meta": {},
      "super_nodes": [{
        "id": "s0",
        "constellations": [{
          "id": "c0",
          "anchor": [0.5, 0.5, 0.5],
          "radial_minmax": [0.0, 1.0],
          "spectrum": [0.25, 0.25, 0.25, 0.25]
        }]
      }]
    }
  }'
```

---

### GET /shape/point/{pid}/jump

Locate the source media for a given point ID. Used for cross-modal navigation (e.g., jumping to a video timestamp from a text point).

**Path parameters:**

| Param | Type | Description |
|-------|------|-------------|
| `pid` | string | Point ID (e.g., `p:a1b2c3d4:0` or `v:VIDEO_ID#t=12.5-15.0`) |

**Response:**

```json
{
  "ok": true,
  "locator": {
    "modality": "video",
    "ref_id": "dQw4w9WgXcQ",
    "t": 12.5
  }
}
```

**Errors:**
- `404` — Point not found
- `503` — ShapeStore unavailable

**Example:**

```bash
curl http://localhost:8086/shape/point/v:dQw4w9WgXcQ%23t%3D12.5-15.0/jump
```

---

## Visualization Endpoints

All visualization endpoints are prefixed with `/viz`.

### POST /viz/constellation.svg

Render a single constellation as an SVG polar plot.

**Query parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `dim_x` | int | 0 | Anchor dimension for X axis |
| `dim_y` | int | 1 | Anchor dimension for Y axis |
| `rotate` | float | 0.0 | Rotation in degrees |

**Request body:** A `Constellation` object.

**Response:** SVG image (`image/svg+xml`).

**Example:**

```bash
curl -X POST http://localhost:8086/viz/constellation.svg \
  -H "Content-Type: application/json" \
  -d '{
    "id": "c0",
    "anchor": [0.5, 0.5, 0.5],
    "radial_minmax": [0.0, 1.0],
    "spectrum": [0.1, 0.3, 0.4, 0.2]
  }' -o constellation.svg
```

---

### GET /viz/shape/{shape_id}.svg

Render a constellation from a stored shape as SVG.

**Path parameters:**

| Param | Type | Description |
|-------|------|-------------|
| `shape_id` | string | The shape ID (16 hex chars) |

**Query parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `super_idx` | int | 0 | Super node index |
| `const_idx` | int | 0 | Constellation index within the super node |
| `dim_x` | int | 0 | Anchor dimension for X axis |
| `dim_y` | int | 1 | Anchor dimension for Y axis |
| `rotate` | float | 0.0 | Rotation in degrees |

**Response:** SVG image (`image/svg+xml`).

**Errors:**
- `400` — Invalid indices
- `404` — Shape not found

**Example:**

```bash
curl http://localhost:8086/viz/shape/a1b2c3d4e5f67890.svg -o shape.svg
```

---

### POST /viz/preview/decode

Decode text from a single constellation (without storing it first).

**Query parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `per_constellation` | int | 20 | Max results |
| `codebook_path` | string | null | Codebook filename |

**Request body:** A `Constellation` object.

**Response:** Same format as `/geometry/decode/text`.

**Example:**

```bash
curl -X POST "http://localhost:8086/viz/preview/decode?per_constellation=5" \
  -H "Content-Type: application/json" \
  -d '{
    "id": "c0",
    "anchor": [0.5, 0.5, 0.5],
    "radial_minmax": [0.0, 1.0],
    "spectrum": [0.25, 0.25, 0.25, 0.25]
  }'
```

---

### POST /viz/mix/decode

Interpolate two constellations and decode text from the mixed result.

**Query parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `per_constellation` | int | 20 | Max results |
| `codebook_path` | string | null | Codebook filename |

**Request body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `const_a` | Constellation | yes | First constellation |
| `const_b` | Constellation | yes | Second constellation |
| `alpha_anchor` | float | no | Interpolation weight for anchors (0.0 = all A, 1.0 = all B; default: 0.5) |
| `alpha_spectrum` | float | no | Interpolation weight for spectra (default: 0.5) |

**Response:** Same format as `/geometry/decode/text`.

---

### POST /viz/preview/calibration

Run calibration on a single constellation without storing it.

**Query parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `codebook_path` | string | null | Codebook filename |

**Request body:** A `Constellation` object.

**Response:** Same format as `/geometry/calibration/report`.

---

### POST /viz/mix/calibration

Interpolate two constellations and run calibration on the mixed result.

**Query parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `codebook_path` | string | null | Codebook filename |

**Request body:** Same as `/viz/mix/decode`.

**Response:** Same format as `/geometry/calibration/report`.

---

### GET /viz/recent

List recently stored shape IDs.

**Query parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `limit` | int | 10 | Max shapes to return |

**Response:**

```json
["a1b2c3d4e5f67890", "f0e1d2c3b4a59678"]
```

---

### GET /viz/shape/{shape_id}/constellations

List all constellations within a stored shape.

**Path parameters:**

| Param | Type | Description |
|-------|------|-------------|
| `shape_id` | string | The shape ID |

**Response:**

```json
{
  "shape_id": "a1b2c3d4e5f67890",
  "constellations": [
    {"super_idx": 0, "const_idx": 0, "id": "c0", "has_points": true},
    {"super_idx": 0, "const_idx": 1, "id": "c1", "has_points": false}
  ]
}
```

**Errors:**
- `404` — Shape not found

---

## Workflow Endpoints

### POST /workflow/demo_run

Run the full CHIT demonstration pipeline: ingest a YouTube video, index in Hi-RAG, build a CGP, decode, calibrate, and index in Neo4j.

**Request body** (`DemoRunRequest`):

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `url` | string | no | YouTube URL to ingest (alias: `youtube_url`) |
| `namespace` | string | no | Indexing namespace (default: `INDEXER_NAMESPACE` env var) |
| `bucket` | string | no | MinIO bucket (default: `YT_BUCKET` env var) |
| `query` | string | no | Query for Hi-RAG retrieval (default: video title) |
| `per_constellation` | int | no | Decode results per constellation (1-100, default: 20) |
| `codebook_path` | string | no | Codebook filename for decode/calibration |
| `cgp` | object | no | Provide a CGP directly for offline mode (skips YouTube ingest) |

**Modes:**

- **Online mode** (default): Ingests a YouTube video, transcribes, indexes, builds CGP, runs full pipeline.
- **Offline mode** (when `cgp` is provided): Skips YouTube ingest, uses the provided CGP directly for decode and calibration.

**Response (online):**

```json
{
  "video": {"video_id": "...", "title": "...", "namespace": "...", "segments_indexed": 6},
  "ingest": {},
  "hirag": {"upsert": {}, "query": {}},
  "shape": {
    "shape_id": "...",
    "constellations": ["vid:00", "vid:01"],
    "data_url": "/data/....json",
    "decode": {"items": []},
    "calibration": {"KL": 0.03, "JS": 0.008, "coverage": 0.87},
    "artifacts": {"reconstruction_report": "/artifacts/reconstruction_report.md"}
  },
  "neo4j": {"points_indexed": 10, "sample": []},
  "playback": null,
  "events": []
}
```

**Response (offline):**

```json
{
  "mode": "offline",
  "shape": {
    "shape_id": "...",
    "constellations": [],
    "data_url": "/data/....json",
    "decode": {"items": []},
    "calibration": {"KL": null, "JS": null, "coverage": 0.0},
    "artifacts": {"reconstruction_report": "/artifacts/reconstruction_report.md"}
  },
  "events": []
}
```

**Example (offline):**

```bash
curl -X POST http://localhost:8086/workflow/demo_run \
  -H "Content-Type: application/json" \
  -d '{
    "cgp": {
      "spec": "chit.cgp.v1.0",
      "meta": {"source": "text", "units_mode": "sentences", "K": 1, "bins": 4, "backend": "all-MiniLM-L6-v2"},
      "super_nodes": [{
        "id": "s0",
        "constellations": [{
          "id": "demo_0",
          "anchor": [0.5, 0.5, 0.5],
          "radial_minmax": [0.0, 1.0],
          "spectrum": [0.25, 0.25, 0.25, 0.25],
          "points": [
            {"id": "p0", "proj": 0.5, "conf": 0.9, "text": "Sample text."}
          ]
        }]
      }]
    }
  }'
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `CHIT_REQUIRE_SIGNATURE` | `false` | When `true`, all CGP ingestion requires valid HMAC signature. `codebook_path` parameter always requires signature when this is `true`. |
| `CHIT_DECRYPT_ANCHORS` | `false` | When `true`, encrypted anchors (`anchor_enc`) are automatically decrypted during ingestion. |
| `CHIT_PASSPHRASE` | `change-me` | Shared secret for HMAC signing and AES-GCM anchor encryption. |
| `CHIT_CODEBOOK_PATH` | `tests/data/codebook.jsonl` | Default codebook file path. When `codebook_path` is provided in requests, only the basename is used and resolved against this directory. |
| `CHIT_LEARNED_TEXT` | `false` | When `true`, decode responses include a `learned` field with keyword summaries or transformer-generated summaries. |
| `CHIT_T5_MODEL` | (none) | HuggingFace model path for transformer-based learned text decoding. Falls back to keyword frequency when unset. |

---

## HMAC Signing

When `CHIT_REQUIRE_SIGNATURE=true`, CGP packets must include a `sig` field with a valid HMAC-SHA256 signature.

### Computing the signature

1. Take the CGP object and remove the `sig` field.
2. Serialize to canonical JSON: `json.dumps(obj, sort_keys=True, separators=(",", ":"))`.
3. Compute HMAC-SHA256 using `CHIT_PASSPHRASE` as the key over the canonical bytes.
4. Base64-encode the resulting digest.

### Attaching the signature

```json
{
  "sig": {
    "alg": "HMAC-SHA256",
    "kid": "my-key-id",
    "ts": 1739001600,
    "hmac": "<base64-encoded-digest>"
  }
}
```

### Verification behavior

- If `sig` is present, the HMAC is verified against the passphrase.
- If `sig` is absent and `CHIT_REQUIRE_SIGNATURE=false`, the request is accepted.
- If `sig` is absent and `CHIT_REQUIRE_SIGNATURE=true`, the request is rejected (400).
- The `codebook_path` parameter always requires a valid signature when `CHIT_REQUIRE_SIGNATURE=true`, regardless of whether `sig` is provided at the top level. This prevents path traversal via unsigned requests.

---

**See also:** [Quickstart](05_QUICKSTART.md) · [CGP v1.0 Specification](CGP_v1.0_SPECIFICATION.md) · [Glossary](00_GLOSSARY.md) · [Back to README](README.md)
