# The GEOMETRY BUS

*How services talk via shapes.*

> **Previously:** [What Is CHIT?](01_WHAT_IS_CHIT.md) explained how information is encoded as geometry. This document explains how that geometry moves between services.

---

## What It Is

The GEOMETRY BUS is a NATS-based event transport layer that carries CGP packets between PMOVES.AI services. Think of it as a postal system for shape-encoded mail: any service can publish a CGP to a known address (a NATS subject), and any interested service can subscribe and react.

The bus uses NATS JetStream for persistent, at-least-once delivery. CGP packets published to the bus are stored for up to 30 days, so late-joining consumers can catch up.

---

## Architecture

```
                         NATS JetStream
                     (GEOMETRY_CGP stream)
                              │
          ┌───────────────────┼───────────────────┐
          │                   │                   │
     ┌────▼─────┐      ┌─────▼─────┐      ┌─────▼──────┐
     │ PRODUCERS │      │ CONSUMERS │      │  BOTH      │
     ├──────────┤      ├───────────┤      ├────────────┤
     │ DeepRes. │      │ Hi-RAG v2 │      │ ShapeStore │
     │ SupaSerch│      │ Discord   │      │            │
     │ Flute GW │      │ Hyperdim  │      │            │
     │ ToKenism │      │           │      │            │
     └──────────┘      └───────────┘      └────────────┘

  Producers publish CGP      Consumers subscribe     ShapeStore ingests
  packets to NATS subjects   and act on geometry     and persists all CGPs
```

**Producers** build CGP packets and publish them when their work completes (e.g., DeepResearch finishes a research query and publishes results as a CGP).

**Consumers** subscribe to CGP subjects and react: Hi-RAG v2 indexes the geometry for retrieval, Publisher-Discord formats it for human notification, Hyperdim renders 3D visualizations.

**ShapeStore** is both consumer and persistence layer — it ingests every CGP, assigns a Shape ID, and stores the packet for later querying.

---

## How a CGP Travels

Here is the life of a CGP packet, step by step:

### Step 1: A service builds a CGP

DeepResearch completes a research query. It structures the results as constellations: each research step becomes a point, grouped into constellations by topic, with spectra derived from quality metrics.

### Step 2: The CGP is published to NATS

```python
await nats_client.publish(
    "tokenism.cgp.ready.v1",
    json.dumps(cgp_packet).encode()
)
```

The packet lands on the `GEOMETRY_CGP` JetStream stream.

### Step 3: Hi-RAG v2 receives the event

Hi-RAG v2 subscribes to `tokenism.cgp.ready.v1`. On receipt, it calls its internal `/geometry/event` handler, which:
- Verifies the HMAC signature (if `CHIT_REQUIRE_SIGNATURE=true`)
- Decrypts any encrypted anchors
- Computes a Shape ID (SHA-256 hash of the canonical packet)
- Assigns point IDs to any points that lack them

### Step 4: ShapeStore caches the CGP

The `shape_store.on_geometry_event()` call indexes all constellations and their points in memory for fast lookup.

### Step 5: The CGP is persisted

The packet is written to `data/{shape_id}.json` on disk, and optionally synced to Supabase for durable storage.

### Step 6: The CGP is queryable

Any service can now:
- Decode text from the shape via `/geometry/decode/text`
- Visualize constellations via `/viz/shape/{shape_id}.svg`
- Jump to source media via `/shape/point/{pid}/jump`
- Run calibration reports via `/geometry/calibration/report`

---

## Key NATS Subjects

| Subject | Direction | Purpose |
|---------|-----------|---------|
| `tokenism.cgp.ready.v1` | Pub → Hi-RAG, Discord, ShapeStore | Generic CGP packet ready for consumption |
| `tokenism.cgp.weekly.v1` | Pub → Discord, Hi-RAG | Weekly ToKenism economic attribution export |
| `tokenism.attribution.recorded.v1` | Pub → Discord, analytics | Real-time attribution notification |
| `tokenism.geometry.event.v1` | Pub → Hi-RAG | Voice/modality attribution events |
| `tokenism.swarm.population.v1` | Pub → analytics, Discord | EVO SWARM population state updates |
| `geometry.cgp.v1` | Pub → Hi-RAG (Supabase RT) | CGP via Supabase Realtime channel |
| `geometry.event.v1` | Pub → ShapeStore | Raw geometry events for persistent storage |
| `geometry.swarm.meta.v1` | Pub → Hi-RAG | Decoder pack metadata for swarm optimization |

For the complete subject catalog with payload examples, see [geometry-nats-subjects.md](../../.claude/context/geometry-nats-subjects.md).

---

## Making Your Service Shape-Native

To have your service publish CGPs to the GEOMETRY BUS:

1. **Build a CGP packet** following the schema in [CGP_v1.0_SPECIFICATION.md](CGP_v1.0_SPECIFICATION.md).
2. **Publish to `tokenism.cgp.ready.v1`** via your NATS client.
3. **Set an environment variable** (e.g., `MY_SERVICE_CGP_PUBLISH=true`) so operators can toggle CGP publishing.

For full code examples in Python and TypeScript, see [GEOMETRY_BUS_INTEGRATION.md](GEOMETRY_BUS_INTEGRATION.md) § Implementing CGP Publishing.

For consuming CGPs, subscribe to the relevant subject and parse the incoming JSON as a CGP document. The schema is backward-compatible: a v1.0 consumer can read v0.1 and v0.2 packets.

---

## What Comes Next

The GEOMETRY BUS carries shapes between services, but who decides if the attribution encoded in those shapes is *fair*? That is the job of **EVO SWARM** — a distributed optimization system that tunes attribution weights without a central authority.

**Next: [EVO SWARM →](03_EVO_SWARM.md)**

---

**See also:** [Glossary](00_GLOSSARY.md) · [GEOMETRY BUS Integration Guide](GEOMETRY_BUS_INTEGRATION.md) · [NATS Subject Catalog](../../.claude/context/geometry-nats-subjects.md) · [Back to README](README.md)
