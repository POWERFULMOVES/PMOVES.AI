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

**Agent Card** — A CGP v0.2 packet encoding an agent's capabilities, taxonomy position, and topology as geometry. Flows through the GEOMETRY BUS for agent coordination. See: [LIVING_TEMPLATE_AGENT_TAXONOMY.md](LIVING_TEMPLATE_AGENT_TAXONOMY.md).

**CONCH (Consciousness Harvest)** — Pipeline for encoding consciousness research datasets into CGP packets and grounding them as personas via Supabase, Hi-RAG v2, and Evo Swarm. See: [PMOVES-CONCHexecution_guide.md](PMOVES-CONCHexecution_guide.md).

**DARKXSIDE** — Creative persona of Cataclysm Studios; the artistic identity layer that personifies the platform's culture of empowerment. See: [CATACLYSM_STUDIOS_INC.md](CATACLYSM_STUDIOS_INC.md).

**Distillation** — Progressive specialization of an agent or model through four stages: `config_tuning` → `context_priming` → `model_fine_tune` → `full_distillation`. Each stage reduces the gap between generic capability and domain-specific performance. See: [THREE_BODY_DOCTRINE.md](THREE_BODY_DOCTRINE.md).

**Flute** — Multimodal Communication Layer providing prosodic voice synthesis with natural pauses and emphasis. Uses GEOMETRY BUS for shape-encoded transport. See: [FLUTE_PROSODIC_ARCHITECTURE.md](../FLUTE_PROSODIC_ARCHITECTURE.md).

**Orbital Resonance** — Stable equilibrium between three-body entities (Human, AI, System). Measured as a stability metric from 0.0 (chaotic) to 1.0 (locked resonance). See: [THREE_BODY_DOCTRINE.md](THREE_BODY_DOCTRINE.md).

**Prosodic Synthesis** — Voice output with natural pauses, emphasis, and breath boundaries. Achieves sub-100ms time-to-first-speech via the Flute sidecar. See: [FLUTE_PROSODIC_ARCHITECTURE.md](../FLUTE_PROSODIC_ARCHITECTURE.md).

**SHIFTEST (Shape Harmonic Intelligence Framework for Testing)** — Conceptual framework and shareable explainer for CHIT. Describes the encoder/decoder/viewer triad. See: [PMOVESSHIFTEST.md](PMOVESSHIFTEST.md).

**Tabula Rasa** — An agent or model's starting state before shape discovery — no geometric priors, no constellation assignments. The distillation process moves an agent from tabula rasa to specialized shape. See: [THREE_BODY_DOCTRINE.md](THREE_BODY_DOCTRINE.md).

**Three-Body Problem** — The dynamic equilibrium model underlying PMOVES: Human, AI, and System orbit each other with mutual influence and non-linear dynamics. CHIT provides the "gravitational field" that keeps all three bodies in resonance. See: [THREE_BODY_DOCTRINE.md](THREE_BODY_DOCTRINE.md).

---

[Back to README](README.md)
