# CHIT Glossary

Quick-reference definitions for terms used throughout the CHIT documentation suite.

---

**Anchor** — A unit vector in embedding space that defines the "direction" of a constellation. All points in the constellation are projected onto this direction to produce their radial positions. See: [CGP_v1.0_SPECIFICATION.md](CGP_v1.0_SPECIFICATION.md) § CGP Schema.

**Builder Pack** — A distribution kit for new CHIT integrators containing sample CGP packets, codebook templates, and integration boilerplate. See: [05_QUICKSTART.md](05_QUICKSTART.md).

**CGP (CHIT Geometry Packet)** — The wire format for CHIT data. A JSON document containing metadata, super nodes, constellations, spectra, and optional signatures. The current production version is `chit.cgp.v1.0`. See: [CGP_v1.0_SPECIFICATION.md](CGP_v1.0_SPECIFICATION.md).

**CHIT (Cymatic-Holographic Information Transfer)** — A geometric protocol that encodes information as boundary representations (constellations of anchors and spectra) instead of raw token streams. The core thesis: meaning has shape, and that shape is enough to reconstruct content. See: [01_WHAT_IS_CHIT.md](01_WHAT_IS_CHIT.md).

**CHR (Constellation Harvest Regularization)** — The encoding algorithm that discovers anchor directions and computes soft assignments of data points to constellations. Optimizes anchors via gradient descent on assignment entropy. See: [CGP_v1.0_SPECIFICATION.md](CGP_v1.0_SPECIFICATION.md) § Encoding Pipeline.

**Codebook** — A shared corpus of embedding vectors (JSONL format) used by the decoder. When encoder and decoder share a codebook, meaning can be reconstructed purely from geometry without transmitting raw text. See: [04_API_REFERENCE.md](04_API_REFERENCE.md) § Environment Variables.

**Confidence** — A point-level metric (`conf` field) representing the assignment strength of a data point to its constellation, derived from the maximum soft-assignment probability. Range: 0.0 to 1.0. See: [CGP_v1.0_SPECIFICATION.md](CGP_v1.0_SPECIFICATION.md) § Field Specifications.

**Constellation** — A cluster within a super node, defined by an anchor direction, radial bounds, and an energy spectrum. The fundamental geometric unit of CHIT encoding. See: [01_WHAT_IS_CHIT.md](01_WHAT_IS_CHIT.md).

**Cross-modal Jump** — Navigating from a point in one modality (e.g., text) to a related point in another modality (e.g., video timestamp) using the `/shape/point/{pid}/jump` endpoint. See: [04_API_REFERENCE.md](04_API_REFERENCE.md).

**Dirichlet Distribution** — A probability distribution over the simplex used as the Bayesian prior for CHIT attribution weights. Guarantees every contributor receives non-zero weight when all concentration parameters are >= 1. See: [CGP_v1.0_SPECIFICATION.md](CGP_v1.0_SPECIFICATION.md) § Dirichlet Distributions.

**EVO SWARM** — A distributed evolutionary optimization system that tunes attribution weights across agents without a central authority. Uses mutation (Dirichlet noise), crossover, and fitness-based selection. See: [03_EVO_SWARM.md](03_EVO_SWARM.md).

**Five Pillars** — The five mathematical foundations of CHIT: (1) Dirichlet Distributions, (2) Hyperbolic Geometry, (3) Merkle Proofs, (4) Zeta Spectral Filtering, (5) Swarm Optimization. See: [01_WHAT_IS_CHIT.md](01_WHAT_IS_CHIT.md) § The Five Pillars.

**GEOMETRY BUS** — The NATS-based event transport layer that carries CGP packets between PMOVES.AI services. Subjects follow the `tokenism.*` and `geometry.*` naming conventions. See: [02_GEOMETRY_BUS.md](02_GEOMETRY_BUS.md).

**Merkle Proof** — A hash-based verification tree that provides tamper-proof attribution chains. Each constellation's contributions can be independently verified against a Merkle root. See: [CGP_v1.0_SPECIFICATION.md](CGP_v1.0_SPECIFICATION.md) § Merkle Proofs.

**MHEP (Multi-scale Hyperbolic Entropy Product)** — A quality metric stored in CGP metadata. Measures how well the encoding captures hierarchical structure across scales. Higher values indicate better encoding quality. See: [CGP_v1.0_SPECIFICATION.md](CGP_v1.0_SPECIFICATION.md) § Field Specifications.

**Poincare Disk** — The hyperbolic geometry model used by CHIT for hierarchical embedding. Represents hyperbolic space as the interior of a unit disk where distance grows exponentially toward the boundary. See: [CGP_v1.0_SPECIFICATION.md](CGP_v1.0_SPECIFICATION.md) § Hyperbolic Geometry.

**Point** — An individual data unit within a constellation (e.g., a sentence, image, audio segment). Contains a projection value, confidence, optional text, and source reference. See: [CGP_v1.0_SPECIFICATION.md](CGP_v1.0_SPECIFICATION.md) § CGP Schema.

**Projection** — A point's scalar position along its constellation's anchor direction (`proj` field). Represents where the point falls within the constellation's radial bounds. See: [01_WHAT_IS_CHIT.md](01_WHAT_IS_CHIT.md) § A Worked Example.

**Radial Bounds** — The `radial_minmax` field on a constellation: a `[min, max]` pair defining the range of valid projections along the anchor. Together with the spectrum, defines the constellation's "shape." See: [CGP_v1.0_SPECIFICATION.md](CGP_v1.0_SPECIFICATION.md) § Field Specifications.

**Shape ID** — A truncated SHA-256 hash (16 hex chars) computed over the canonical JSON representation of a CGP packet (excluding the `sig` field). Used as the primary identifier for stored shapes. See: [04_API_REFERENCE.md](04_API_REFERENCE.md).

**ShapeStore** — The persistence layer that stores ingested CGP packets and constellation data. Backed by local JSON files and optionally Supabase. See: [02_GEOMETRY_BUS.md](02_GEOMETRY_BUS.md) § How a CGP Travels.

**Spectrum** — An array of floats on a constellation representing the energy distribution across radial bins. Functions as a histogram of data density along the anchor direction. Values sum to 1.0. See: [01_WHAT_IS_CHIT.md](01_WHAT_IS_CHIT.md).

**SuperNode** — A top-level grouping within a CGP packet that contains one or more constellations. Represents a resonant mode or major semantic cluster. See: [CGP_v1.0_SPECIFICATION.md](CGP_v1.0_SPECIFICATION.md) § CGP Schema.

**Zeta Filter** — A signal processing technique that uses the non-trivial zeros of the Riemann zeta function as filter frequencies. Enhances meaningful patterns in spectra while suppressing noise. See: [CGP_v1.0_SPECIFICATION.md](CGP_v1.0_SPECIFICATION.md) § Zeta Spectral Filtering.

---

[Back to README](README.md)
