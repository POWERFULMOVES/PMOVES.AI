# CHIT Quickstart

Six runnable examples to get from zero to working CGP in five minutes.

**Prerequisites:**
- PMOVES Gateway running at `http://localhost:8086` (default via `make up-gateway`)
- `curl` and `jq` installed
- For Example 6: NATS CLI (`nats`) installed and connected to `localhost:4222`

---

## Example 1: Ingest a CGP Packet

The simplest possible interaction: publish a minimal CGP and get back a Shape ID.

```bash
# Ingest a single-constellation CGP about "urban farming"
curl -s -X POST http://localhost:8086/geometry/event \
  -H "Content-Type: application/json" \
  -d '{
    "type": "chit.cgp.v1.0",
    "data": {
      "spec": "chit.cgp.v1.0",
      "meta": {
        "source": "text",
        "units_mode": "sentences",
        "K": 1,
        "bins": 4,
        "backend": "sentence-transformers/all-MiniLM-L6-v2"
      },
      "super_nodes": [{
        "id": "super_0",
        "constellations": [{
          "id": "urban_farming",
          "anchor": [0.42, -0.18, 0.67, 0.31],
          "radial_minmax": [-0.22, 0.85],
          "spectrum": [0.10, 0.35, 0.40, 0.15],
          "points": [
            {"id": "pt_0", "proj": 0.12, "conf": 0.91, "text": "Rooftop gardens reduce urban heat islands."},
            {"id": "pt_1", "proj": 0.55, "conf": 0.87, "text": "Community plots increase food security."},
            {"id": "pt_2", "proj": 0.78, "conf": 0.93, "text": "Vertical farms use 95% less water."}
          ]
        }]
      }]
    }
  }' | jq .

# Expected output:
# {
#   "ok": true,
#   "shape_id": "a1b2c3d4e5f67890",
#   "event": "chit.cgp.v1.0"
# }
```

Save the `shape_id` — you will use it in the next examples.

---

## Example 2: Visualize a Constellation

Render the stored constellation as an SVG polar plot and open it in your browser.

```bash
# Replace SHAPE_ID with the value from Example 1
SHAPE_ID="a1b2c3d4e5f67890"

# Fetch the SVG for the first constellation of the first super node
curl -s "http://localhost:8086/viz/shape/${SHAPE_ID}.svg" -o constellation.svg

# Open in browser (macOS)
open constellation.svg

# Open in browser (Linux)
xdg-open constellation.svg

# Open in browser (Windows)
start constellation.svg
```

The SVG shows:
- **Cyan arrow** — the anchor direction (projected to 2D from `dim_x=0, dim_y=1`)
- **Colored radial bars** — spectrum energy per bin
- **Concentric rings** — reference grid

Try different projection axes: `?dim_x=0&dim_y=2` or add rotation: `?rotate=45`.

---

## Example 3: Decode Text from Geometry

Use the geometry-only decoder to find codebook entries that match the constellation's shape.

```bash
SHAPE_ID="a1b2c3d4e5f67890"

curl -s -X POST http://localhost:8086/geometry/decode/text \
  -H "Content-Type: application/json" \
  -d "{
    \"shape_id\": \"${SHAPE_ID}\",
    \"per_constellation\": 5
  }" | jq '.items[:3]'

# Expected output (depends on codebook contents):
# [
#   {
#     "constellation_id": "urban_farming",
#     "text": "closest matching codebook entry",
#     "proj_est": 0.73,
#     "score": 0.92
#   },
#   ...
# ]
```

**How it works:** The decoder projects every codebook vector onto the `anchor` direction, bins the projections, and scores each entry by how well its bin matches the `spectrum`. High-scoring entries are the codebook's best geometric matches for this constellation.

If the codebook is empty or not found, you will get `{"items": []}`. See [Environment Variables](04_API_REFERENCE.md#environment-variables) for configuring `CHIT_CODEBOOK_PATH`.

---

## Example 4: Mix Two Constellations

Interpolate between two constellations to explore the geometric space between them.

```bash
# Mix two constellations with 70% weight on A's anchor, 50% on A's spectrum
curl -s -X POST "http://localhost:8086/viz/mix/decode?per_constellation=5" \
  -H "Content-Type: application/json" \
  -d '{
    "const_a": {
      "id": "farming",
      "anchor": [0.42, -0.18, 0.67, 0.31],
      "radial_minmax": [-0.22, 0.85],
      "spectrum": [0.10, 0.35, 0.40, 0.15]
    },
    "const_b": {
      "id": "technology",
      "anchor": [0.71, 0.33, -0.12, 0.55],
      "radial_minmax": [0.10, 0.95],
      "spectrum": [0.30, 0.25, 0.20, 0.25]
    },
    "alpha_anchor": 0.3,
    "alpha_spectrum": 0.5
  }' | jq .

# The result is decoded text for the mixed constellation: "mix:farming|technology"
# With alpha_anchor=0.3, the mixed anchor leans 70% toward farming.
# With alpha_spectrum=0.5, the spectrum is an even blend.
```

This is useful for exploring semantic interpolation — what lies "between" two topics in geometric space.

---

## Example 5: Run the Full Demo Pipeline (Offline Mode)

Run the complete CHIT pipeline without external service dependencies by providing a CGP directly.

```bash
curl -s -X POST http://localhost:8086/workflow/demo_run \
  -H "Content-Type: application/json" \
  -d '{
    "cgp": {
      "spec": "chit.cgp.v1.0",
      "meta": {
        "source": "text",
        "units_mode": "sentences",
        "K": 2,
        "bins": 4,
        "backend": "sentence-transformers/all-MiniLM-L6-v2"
      },
      "super_nodes": [{
        "id": "demo_node",
        "constellations": [
          {
            "id": "topic_a",
            "anchor": [0.5, 0.5, 0.0],
            "radial_minmax": [0.0, 1.0],
            "spectrum": [0.1, 0.4, 0.4, 0.1],
            "points": [
              {"id": "p0", "proj": 0.3, "conf": 0.9, "text": "First sentence of topic A."},
              {"id": "p1", "proj": 0.7, "conf": 0.85, "text": "Second sentence of topic A."}
            ]
          },
          {
            "id": "topic_b",
            "anchor": [0.0, 0.5, 0.5],
            "radial_minmax": [0.0, 1.0],
            "spectrum": [0.3, 0.2, 0.2, 0.3],
            "points": [
              {"id": "p2", "proj": 0.5, "conf": 0.88, "text": "First sentence of topic B."}
            ]
          }
        ]
      }]
    },
    "per_constellation": 3
  }' | jq '{mode, shape_id: .shape.shape_id, constellations: .shape.constellations, calibration: .shape.calibration}'

# Expected output:
# {
#   "mode": "offline",
#   "shape_id": "...",
#   "constellations": ["topic_a", "topic_b"],
#   "calibration": {"KL": ..., "JS": ..., "coverage": ...}
# }
```

The offline pipeline:
1. Ingests the CGP into ShapeStore
2. Computes a Shape ID
3. Decodes text from the stored constellations
4. Runs calibration (KL/JS divergence, coverage)

---

## Example 6: Publish to the GEOMETRY BUS

Publish a CGP event directly to NATS so that all subscribed services (Hi-RAG, Discord, ShapeStore) receive it.

```bash
# Publish a test CGP packet to the GEOMETRY BUS
nats pub "tokenism.cgp.ready.v1" '{
  "spec": "chit.cgp.v1.0",
  "summary": "Quickstart test packet",
  "created_at": "2026-02-18T12:00:00Z",
  "super_nodes": [{
    "id": "quickstart:test",
    "label": "test",
    "summary": "Quickstart example CGP",
    "constellations": [{
      "id": "quickstart.test.c0",
      "summary": "Test constellation",
      "anchor": [0.5, 0.5, 0.5],
      "spectrum": [0.5, 0.3, 0.2],
      "points": [{
        "id": "quickstart:p0",
        "modality": "text",
        "proj": 1.0,
        "conf": 0.9,
        "summary": "Hello from the quickstart guide"
      }],
      "meta": {"namespace": "quickstart"}
    }]
  }],
  "meta": {"source": "quickstart.manual.v1", "tags": ["test"]}
}'

# Monitor events in another terminal:
# nats sub "tokenism.cgp.ready.v1" --max 5
```

When Hi-RAG v2 receives this event, it will process the packet through `/geometry/event` and store it in the ShapeStore. Publisher-Discord will format it as a Discord embed.

---

## Next Steps

- **Explore the API** — See [API Reference](04_API_REFERENCE.md) for all 13 endpoints
- **Understand the concepts** — Read [What Is CHIT?](01_WHAT_IS_CHIT.md) for the full story
- **Integrate your service** — See [GEOMETRY BUS Integration Guide](GEOMETRY_BUS_INTEGRATION.md) for code examples in Python and TypeScript
- **Read the spec** — See [CGP v1.0 Specification](CGP_v1.0_SPECIFICATION.md) for the canonical schema

---

**See also:** [API Reference](04_API_REFERENCE.md) · [Glossary](00_GLOSSARY.md) · [Back to README](README.md)
