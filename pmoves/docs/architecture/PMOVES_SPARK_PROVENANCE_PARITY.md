# PMOVES SPARK Provenance Parity Contract
_Last updated: 2026-04-25_

**Status:** Working Contract

This document turns the current SPARK lane from "GPU node available" into a
real parity contract for message shaping, provenance, HiRAG gating, and
Hyperdimensions-driven creator surfaces.

It exists for one reason: raw content should not slide straight into HiRAG.
PMOVES needs a pass that shapes the message, extracts the lexicon, scores the
signal, proves the lineage, and only then lets it become retrieval or art.

## Operator Language -> Repo Language

| What the operator means | PMOVES implementation surface |
| --- | --- |
| "junk doesn't go into HiRAG" | provenance-first ingest gate with accept/reject subjects and quarantine review lane |
| "contextual shape, lexicon, favorite words" | SPARK shaping pass that extracts anchors, clusters, aliases, and weighted term geometry |
| "mapping by result to the merkle" | per-message or per-run Merkle leaves built from canonical term-weight-source tuples |
| "if I say the word, show the semantic and relative weight" | Hyperdimensions node overlay with size, position, opacity, and spectrum driven by the weighted lexicon |
| "make the chimeras of the data" | cross-modal CHIT scene that fuses text, audio, provenance, and geometry into one replayable surface |
| "dynamically tune the spectra" | zeta-filtered controls over `delta`, `kappa`, `Hz`, fitness, and attribution confidence |

## Canonical Surfaces

| Surface | Role |
| --- | --- |
| `pmoves/docs/AGENTS/AGNOTE-dgx-spark.md` | SPARK node note and owner-facing status |
| `pmoves/configs/tac_trees/dgx-spark.tac.yaml` | SPARK TAC tree for node health and mesh integration |
| `pmoves/docs/AGENTS/PMOVES_HYPERDIMENSIONS_CONTROL_PLANE.md` | runtime control-vector contract for Hyperdimensions |
| `pmoves/docs/CONCH_INTEGRATION_MAP.md` | existing CHIT/CGP publish path into HiRAG |
| `pmoves/docs/GRAPHITI_PROTOCOL_REFERENCE.md` | cryptographic provenance contract |
| `pmoves/docs/TOKENISM_DEVELOPER_GUIDE.md` | Merkle attribution and proof vocabulary |
| `pmoves/tools/chit_encode_hook.py` | pre-index CHIT shaping hook |
| `pmoves/tools/zeta_filter.py` | spectral weighting/filtering utility |
| `pmoves/tools/publish_handshake.py` | shape capsule replay/event handoff |

## Node Roles

| Node / plane | Responsibility |
| --- | --- |
| `z890` | NATS subjects, JetStream retention, HiRAG gate policy, provenance contract, docs canon |
| `pmoves-dgx-spark` | heavy shaping inference, lexicon extraction, semantic weighting, multimodal scoring |
| `HiRAG v2` | retrieval/indexing sink that only accepts attested payloads |
| `Hyperdimensions` | visualization, tuning, replay, and creator-facing control surface |
| `Graphiti + ToKenism` | provenance marks, canonicalization, Merkle root + proof chain |

## Provenance-First Message Flow

### Rule

No raw message, transcript, note, DM, upload, or automation artifact should be
indexed directly into HiRAG without a shaping pass and an attestation pass.

### Event chain

| Stage | Subject / surface | Status | Owner |
| --- | --- | --- | --- |
| Raw intake | `content.raw.v1` | Proposed | `z890` |
| Lexicon shaping | `content.lexicon.shaped.v1` | Proposed | `pmoves-dgx-spark` |
| Provenance attestation | `content.provenance.attested.v1` | Proposed | `z890` + Graphiti/ToKenism |
| HiRAG accept lane | `content.hirag.accepted.v1` | Proposed | `z890` |
| HiRAG reject lane | `content.hirag.rejected.v1` | Proposed | `z890` |
| Geometry publish | `geometry.cgp.v1` | Existing | HiRAG / CONCH |
| Shape replay | `mesh.shape.handshake.v1` | Existing | Hyperdimensions |
| Control vector | `hyperdimensions.control.v1` | Backlog | Hyperdimensions |

### Gate semantics

`content.hirag.accepted.v1` is emitted only if all of the following are true:

1. `noise_score` is below the configured threshold.
2. `semantic_density` is above the configured threshold.
3. `dedupe_score` does not indicate near-duplicate noise.
4. At least one lexicon anchor and one replayable source locator exist.
5. `graphiti_mark`, `shape_id`, and `merkle_root` are present.
6. The payload can be canonicalized and re-hashed without drift.

Everything else goes to `content.hirag.rejected.v1` with a reason code. Rejected
content is still useful: it becomes review material, training material, or art
material, but not retrieval truth.

## Canonical Shaped Envelope

```json
{
  "type": "content.provenance.attested.v1",
  "data": {
    "shape_id": "sha256:...",
    "source": {
      "kind": "message",
      "locator": "discord/channel/thread/message-id",
      "observed_at": "2026-04-25T18:30:00Z"
    },
    "lexicon": {
      "anchors": ["mof", "maf", "art", "self-discovery"],
      "favorite_words": ["resonance", "spectrum", "shape"],
      "alias_clusters": [
        { "label": "geometry", "terms": ["shape", "vector", "constellation"] }
      ]
    },
    "weights": {
      "semantic": { "art": 0.84, "business": 0.32, "ops": 0.27, "self": 0.91 },
      "dirichlet": { "conceptual": 0.42, "contextual": 0.29, "relational": 0.19 }
    },
    "quality": {
      "noise_score": 0.18,
      "semantic_density": 0.77,
      "dedupe_score": 0.11,
      "attribution_confidence": 0.93
    },
    "provenance": {
      "graphiti_mark": "PHI-4482-GATEWAY::PMOVES",
      "merkle_root": "0x...",
      "model_lineage": ["ollama_spark/gemma4:31b"],
      "canonical_hash": "sha256:..."
    }
  }
}
```

## Lexicon -> Merkle Mapping

The operator goal is not just "tokenize text." It is to preserve what a word
means in relation to surrounding words, intent, and emotional weight.

For this lane, the canonical leaf shape is:

```text
leaf = sha256(
  canonical_json({
    "term": "<normalized term>",
    "cluster": "<semantic cluster id>",
    "weight": <relative weight>,
    "shape_id": "<shape id>",
    "source_locator": "<message or artifact locator>"
  })
)
```

That gives PMOVES three things at once:

1. A verifiable Merkle path for attribution and audit.
2. A stable geometry anchor for Hyperdimensions replay.
3. A portable semantic unit that can be compared across runs.

## Hyperdimensions Creator Surface

Hyperdimensions should render the shaped message as a living scene, not as a
flat debug panel.

| Signal | Visual mapping |
| --- | --- |
| lexicon anchor | node label / selectable term |
| relative weight | node size |
| hyperbolic angle / radius | position in the Poincare surface |
| zeta-filtered spectrum | color band + oscillation |
| attribution confidence | opacity / halo strength |
| provenance state | ring color (`accepted`, `review`, `rejected`) |
| modality | glyph family (`text`, `audio`, `image`, `mixed`) |

The control surface should support:

1. scrubbing the replay timeline by `shape_id`
2. turning spectral bands up/down and watching neighbor terms move
3. isolating one anchor word and seeing related clusters, proofs, and source
4. routing accepted scenes into creator outputs such as video, live overlays,
   and beat-reactive render passes

This is the bridge between CHIT math and the "chimera" art lane the operator is
describing.

## Implementation Slices

### Slice 1: Message Hygiene Gate (`z890`)

- stand up the `content.*` subject family with JetStream retention
- add an accept/reject contract in front of HiRAG ingest
- refuse direct raw indexing except for explicitly marked test fixtures
- record reject reasons for later tuning instead of dropping them silently

### Slice 2: SPARK Lexicon Shaper (`pmoves-dgx-spark`)

- run the shaping pass on raw content using SPARK-hosted models
- extract anchors, favorite words, alias clusters, and relative weights
- compute noise, density, and novelty metrics before attestation
- emit lineage so the model family used for shaping is always visible

### Slice 3: Provenance + Merkle (`z890` + Graphiti/ToKenism)

- canonicalize shaped payloads
- mint `shape_id`
- create Merkle leaves from weighted lexicon entries
- attach `graphiti_mark`, `merkle_root`, and proof references before publish

### Slice 4: Hyperdimensions + Art (`shared`)

- consume shaped/attested packets via `mesh.shape.handshake.v1`
- render the word-weight scene with spectral controls
- bind audio-reactive behavior to existing CHIT/beat tools where useful
- preserve replay artifacts so a scene can be revisited, tuned, and exported

### Slice 5: Docs Provenance Cleanup (`z890`)

- mark canon vs working vs superseded docs explicitly
- keep this file, `DOCUMENTATION_MAP.md`, and `CHIT_CHANGE_TRACKER.md` in sync
- stop using orphan notes as source of truth unless a canonical doc points to them

## Canon Rules For This Lane

1. `PMOVES_SPARK_PROVENANCE_PARITY.md` is the working contract for SPARK-driven
   message shaping and HiRAG provenance gating.
2. `PMOVES_HYPERDIMENSIONS_CONTROL_PLANE.md` remains the control-vector contract
   for `delta`, `kappa`, `Hz`, `F`, and attribution.
3. `GRAPHITI_PROTOCOL_REFERENCE.md` remains the provenance-signing contract.
4. `TOKENISM_DEVELOPER_GUIDE.md` remains the Merkle proof reference.
5. Historical CHIT math docs may inform implementation, but they are not the
   acceptance gate unless named here or in `DOCUMENTATION_MAP.md`.

## Immediate Next Moves

1. Add the `content.*` subject family and retention policy beside the existing
   SPARK `mesh.gpu.*` streams.
2. Wire a shaping worker on SPARK that emits `content.lexicon.shaped.v1`.
3. Add a provenance gate on `z890` that emits accepted vs rejected HiRAG events.
4. Teach Hyperdimensions to load the shaped lexicon envelope and replay it as a
   term-weight scene instead of only generic geometry points.
