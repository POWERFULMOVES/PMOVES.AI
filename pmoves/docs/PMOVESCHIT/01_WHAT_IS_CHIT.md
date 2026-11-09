# What Is CHIT?

*From ideas-have-shapes to working code in 10 minutes.*

> **CHIT** carries two meanings by design. As a *concept* it is **Cymatic Holographic Information Theory** — meaning encoded as geometry instead of long token streams: a small "shape packet" reliably reconstructs the same meaning on the other side, a "neural esperanto" for high-dimensional AI communication. As a *mechanism* it is **Compressed Hierarchical Information Transfer** — the signing + transport layer that moves those packets over the GEOMETRY BUS (NATS) and Hi-RAG retrieval. If it works, humans and AIs communicate more directly — fewer tokens, less ambiguity, richer meaning per message. (See [00_GLOSSARY.md](00_GLOSSARY.md) for the canon.)

---

## The Problem

Modern AI systems communicate by shipping huge streams of tokens back and forth. This works, but it is:

- **Expensive.** A long prompt costs real money and real latency.
- **Lossy.** Context windows truncate. Summaries drift. Information decays at every hop.
- **Ambiguous.** The word "bank" means a dozen things. Tokens carry no structural context about *which* meaning is active.

What if, instead of describing a thought word-by-word, you could transmit its *shape* — and let the receiver reconstruct the words from that shape?

---

## The Insight

Information has geometry.

When you embed a collection of sentences into a vector space (using any standard embedding model), the resulting points are not random. They cluster. Those clusters have:

- **Directions** — some axes capture more variance than others.
- **Densities** — some regions of the axis are rich with data; others are sparse.
- **Hierarchies** — broad topics contain narrower sub-topics, which contain finer sub-topics, like a tree.

CHIT captures these three properties in a compact packet and throws away the raw tokens. The receiver, given the same embedding model and a shared corpus, can look at the shape and pull back text that matches.

Think of it like a star chart. You don't transmit every photon from the night sky — you record the positions and brightnesses of the stars. Anyone with a telescope pointed at the same sky can verify your chart and see the same constellations.

---

## How It Works

### Encoding: Making the Star Chart

Given a document (text, images, audio — anything embeddable):

1. **Embed** — Run every unit (sentence, paragraph, frame) through an embedding model. You now have a cloud of high-dimensional points.
2. **Harvest** — The CHR (Constellation Harvest Regularization) algorithm discovers K cluster directions ("anchors") and assigns each point to its nearest constellation.
3. **Measure** — For each constellation, project all assigned points onto the anchor direction. Bin the projections into a histogram. That histogram is the "spectrum."
4. **Package** — Bundle the anchors, spectra, radial bounds, and optional point metadata into a CGP (CHIT Geometry Packet).

The CGP is your star chart.

### The CGP: A Weather Map for Meaning

A CGP is a JSON document. At its core:

```
CGP
 └─ super_nodes[]          # major semantic regions
     └─ constellations[]   # clusters within each region
         ├─ anchor          # direction vector (the "where")
         ├─ spectrum         # energy histogram (the "how much")
         ├─ radial_minmax    # bounds (the "range")
         └─ points[]         # optional raw data
```

If the analogy is weather: a super node is a continent, a constellation is a weather system, the anchor is wind direction, and the spectrum is the pressure distribution along that direction.

### Decoding: Reading the Chart

Two modes:

- **Exact mode** — If the CGP carries the raw text inside `points[].text`, you just read it. Lossless.
- **Geometry-only mode** — If raw text is omitted, the decoder projects every entry in a shared codebook (corpus) onto each anchor, matches the resulting distribution against the target spectrum, and returns the best-matching entries. The shape alone is enough to reconstruct meaning.

### Why "Holographic"?

In physics, the holographic principle says the information inside a volume can be fully described by data encoded on its boundary. CHIT works the same way: a high-dimensional embedding cloud (the "volume") is encoded as boundary data (anchors + spectra on the surface of the constellation). The boundary is smaller, but it captures the essential structure.

---

## The Five Pillars

CHIT rests on five mathematical foundations. You do not need to understand the math to use CHIT — but knowing the pillars exist helps you understand *why* things work.

**1. Dirichlet Distributions** — Fair weight allocation. When multiple contributors create content, their attribution weights are drawn from a Dirichlet distribution. This guarantees every contributor gets a non-zero share, and the weights update cleanly as new evidence arrives. *Technical hook:* conjugate prior for the multinomial, closed-form Bayesian update. See `dirichlet-weights.ts`.

**2. Hyperbolic Geometry (Poincare Disk)** — Hierarchical capacity. Standard flat vector spaces struggle to represent trees. Hyperbolic space grows exponentially from center to edge, making it a natural fit for taxonomies and knowledge graphs. CHIT can optionally encode constellations on the Poincare disk for richer hierarchy representation. *Technical hook:* curvature K = -1, Mobius addition, O(log n) tree distortion. See `hyperbolic-encoder.ts`.

**3. Merkle Proofs** — Tamper-proof attribution. Every contribution recorded in a CGP can be independently verified against a Merkle root hash. If someone tampers with a weight or removes a contributor, the proof fails. *Technical hook:* SHA-256 leaf hashes, inclusion proofs. See `shape-attribution.ts`.

**4. Zeta Spectral Filtering** — Signal from noise. The non-trivial zeros of the Riemann zeta function (14.13, 21.02, 25.01...) turn out to be useful as natural frequency filters. CHIT applies Gaussian kernels centered on these zeros to separate meaningful spectral patterns from noise. *Technical hook:* Gaussian kernel weighting around zeta zeros, scale-invariant filtering. See `zeta-filter.ts`.

**5. Swarm Optimization (EVO SWARM)** — Distributed consensus. Instead of training a central model, a population of agents each propose attribution weights, mutate them with Dirichlet noise, and select survivors by fitness. No backpropagation, no central authority. *Technical hook:* evolutionary algorithm with entropy-reduction fitness. See `swarm-attribution.ts`.

---

## A Worked Example

Here is a minimal CGP for a single constellation encoding three sentences about urban farming:

```json
{
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
        {"id": "pt_1", "proj": 0.55, "conf": 0.87, "text": "Community plots increase neighborhood food security."},
        {"id": "pt_2", "proj": 0.78, "conf": 0.93, "text": "Vertical farms use 95% less water than field agriculture."}
      ]
    }]
  }]
}
```

Reading this packet:

| Field | Meaning |
|-------|---------|
| `anchor` | The direction in embedding space where this cluster lives. A 4D unit vector (truncated from the full 384D for readability). |
| `radial_minmax` | The projection range: points land between -0.22 and 0.85 along the anchor. |
| `spectrum` | Energy distribution: 10% of data density in bin 1, 35% in bin 2, 40% in bin 3, 15% in bin 4. Most content clusters in the middle-to-upper range. |
| `proj` | Each point's scalar position along the anchor. pt_0 at 0.12 is near the low end; pt_2 at 0.78 is near the high end. |
| `conf` | Assignment confidence: all three points strongly belong to this constellation (>0.85). |

To decode this packet against a codebook without using the embedded text:

```bash
curl -X POST http://localhost:8086/geometry/decode/text \
  -H "Content-Type: application/json" \
  -d '{
    "constellation_ids": ["urban_farming"],
    "per_constellation": 5
  }'
```

The decoder projects every codebook entry onto the anchor, matches the spectrum, and returns the top-scoring entries — which, if the codebook covers the same domain, will be about urban farming.

---

## What Comes Next

A single CGP sitting on disk is useful. But the real power comes when CGPs *flow between services* — when one service encodes meaning as geometry and another service consumes that geometry to act on it.

That transport layer is the **GEOMETRY BUS**: a NATS-based event system that carries shape-encoded packets across the entire PMOVES.AI platform.

**Next: [The GEOMETRY BUS →](02_GEOMETRY_BUS.md)**

---

**See also:** [Glossary](00_GLOSSARY.md) · [API Reference](04_API_REFERENCE.md) · [Quickstart](05_QUICKSTART.md) · [Back to README](README.md)
