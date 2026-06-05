# WS-A — Audio Grounding Layer (Design Spec)

**Date:** 2026-06-03 · **Author:** 4090-claude · **Status:** draft for review
**Program:** "Properly utilize Hyperdimensions" (WS-A keystone of A–E; see `research/HYPERDIMENSIONS_UTILIZATION_PLAN.md`)

## 1. Goal

Replace the impoverished audio analysis (ffprobe + ffmpeg-lavfi → 4 scalars) with a **rich, open, reproducible audio-grounding layer** so that every downstream hologram is **provably tied to measured audio signal** — "scientific, not parlor tricks." WS-A includes a CLAP **embedding microservice** as a MOF lattice node and emits **CGP v2** (CHIT) packets.

## 2. Principles (non-negotiable)

- **Open-source only** (Apache/MIT/BSD/ISC; never CC-BY-NC). See `feedback_open_source_only`.
- **Model can model, tool can tool** — deterministic tools do reproducible grounding; models do only semantic judgment, escalated. See `feedback_tool_deterministic_model_semantic`.
- **CHIT-native, current contract** — emit **CGP v2** (`pmoves/contracts/schemas/geometry/cgp.v2.schema.json`), `spec: "chit.cgp.v0.2"` (backwards-compat with all v1 consumers), populating the v2 extensions (`hyperbolic`, `attribution`, `sig`). The embedding→geometry transform **is** CHIT's hyperbolic encoding — not hand-rolled.
- **MOF** — capacity-class pore (runs where compute is), NATS-native, room-aware (P7), CHIT-signed provenance.

## 3. Two tiers

| Tier | Components | License | Determinism |
|---|---|---|---|
| **Deterministic tools** (grounding) | `librosa` (beat/tempo, chroma→key, MFCC, spectral-contrast, tonnetz, onset); **CLAP** `laion/larger_clap_music` (audio↔text embeddings) as a fixed feature extractor; **AST** `MIT/ast-finetuned-audioset` (527 AudioSet tags) | ISC / Apache-2.0 / BSD-3 | reproducible (pinned revs + params → same hash) |
| **Semantic models** (escalation only) | open audio-LLM: `Qwen/Qwen2-Audio-7B-Instruct` **and** `stepfun-ai/Step-Audio-2-mini` (both Apache-2.0) — semantic description when the deterministic tier is ambiguous (low silhouette) | Apache-2.0 | non-deterministic; used sparingly |

**Model selection is config/registry-driven, never hardcoded.** Every model slot — the CLAP embedder, the AST tagger, and the semantic audio-LLM — is selected via `pmoves-model-registry` (8110) + env/config, not pinned in code. Both semantic models stay available (operator/room picks per workload). The AST slot is explicitly **pluggable across variants** — including NVIDIA audio taggers — to exploit the **SPARK GB10 (Grace-Blackwell) NVIDIA integration**; capacity-class routing sends heavier NVIDIA AST/embedding variants to SPARK/5090 and the light defaults elsewhere. Each selected model's id+revision+license is recorded in the CGP `meta` provenance.

## 4. Components (three bounded units)

### 4.1 `clap-embed` microservice (new MOF lattice node)
- **Purpose:** stateless deterministic embedder. Loads `laion/larger_clap_music`.
- **HTTP API:** `POST /embed/audio` (multipart wav/mp3 → `{embedding:[512], model_rev, sr}`), `POST /embed/text` (→ 512-d, for semantic text queries), `GET /healthz`, `GET /metrics` (Prometheus).
- **Optional NATS** (transport = HTTP **+ optional NATS** per decision): responder on `audio.embed.request.v1` → `audio.embed.result.v1`; honors `context_id` / `X-Context-ID` correlation.
- **Port:** `8112` — in the AI/CHIT service tier (~8086–8113, alongside Hi-RAG/model-registry/evo); verify free against `.claude/CATALOG.md` at impl.
- **Deterministic clip/window:** pin the CLAP audio **clip length + hop** (e.g. fixed 10s windows, mean-pooled) as a reproducibility param, consistent across all tracks and tiers — same audio segmentation → same embedding.
- **Capacity-class / multi-arch:** torch via the repo's `torch.js` per-arch pattern — nvidia `cu128` (4090 sm_89 + 5090 sm_120), Spark GB10 → **NVIDIA arm64 PyTorch container** (SM_110), Knuckles ROCm gfx1201 → **CPU wheel default** (small model), CPU/MPS fallback (MPS = fp32 + `PYTORCH_ENABLE_MPS_FALLBACK=1`). Pin Python 3.10–3.12 (numba/llvmlite aarch64). Post-install check: `torch.cuda.get_arch_list()` + `import librosa,numba`.
- **Registry:** registered in `pmoves-model-registry` (8110) with model id, revision, license, provenance.

### 4.2 `analyze_beats.py` upgrade (the analyzer)
- Per track, deterministic tier: librosa interpretable features + CLAP embedding (via `clap-embed`) + optional AST tags. Assemble a **rich fingerprint** (replaces the 4-scalar record; superset, backward-compatible).
- **Clustering** on CLAP embeddings (k-means/HDBSCAN), **silhouette-validated** (already present); low score → flag low-confidence (don't fabricate) and *optionally* escalate to the semantic tier (open audio-LLM) for description — the only model call.
- The `gaze` sense-mode swaps proprietary Qwen2-Audio-via-Ollama for the **open** semantic tier; `peek`/`glaze` unchanged.
- Output: enriched fingerprints + `groups_summary` (superset schema), **CHIT-signed**.

### 4.3 CGP v2 emission (the contract) — `beats_to_cgp.py` bump
Emit packets validating against `cgp.v2.schema.json`, `spec:"chit.cgp.v0.2"`, populating:
- `super_nodes[].constellations[].points[]` — track = point (modality `audio`), group = constellation, with `spectrum[]` (interpretable feature vector) and `anchor` (group centroid). *(existing structure, kept)*
- **`hyperbolic`** — encode the CLAP embedding into the **Poincaré disk** (`poincare_point` x,y,r,θ,depth,parent_id); hierarchy = group→track. **This is the canonical embedding→geometry transform** (CHIT math), consumed by WS-B/viewer. `space:"poincare_disk"`, `curvature:-1`, `max_radius:0.95`.
- **`attribution`** — Dirichlet α over contributing tracks/features + `contributors[]` (weight = α_i/Σα) + `merkle_root`; provenance/contribution tracking.
- **`sig`** — CHIT HMAC signature (alg/kid/ts/hmac) via the existing CHIT signing path (`pmoves-chit-sign`).
- `meta` — model ids+revisions, feature params, `context_id`, provenance. `state_vector` in `control_plane` retained (back-compat).

## 5. Media source — Jellyfin (current-dev aligned)
Audio comes from the **Jellyfin music library** via the **Jellyfin Bridge (`:8093`)**; fingerprints link back by **Jellyfin item id** (provenance). A **backfill mode** processes the existing library (mirrors `JELLYFIN_BACKFILL_PLAN.md`, but for *audio analysis*, not just metadata). **Note (pre-CHIT debt):** the Jellyfin bridge/backfill docs (2025-10-14) use the old `content.published.v1` / Agent-Zero `/events/publish` pattern — flagged for a **CHIT bump** to CHIT-signed CGP events (tracked under WS-E/docs, out of WS-A code scope).

## 6. Data flow
```
Jellyfin music library ──(bridge :8093, item_id)──▶ analyze_beats.py
   ├─ librosa features (CPU, deterministic)
   ├─ clap-embed (:8112 / NATS) → 512-d audio embedding   ◀── MOF capacity-class node
   └─ AST tags (optional)            ┌─ low silhouette? → open audio-LLM (semantic, escalated)
   → cluster (silhouette-validated) ─┘
   → CHIT-sign → beats_to_cgp.py → CGP v2 (hyperbolic + attribution + sig) → NATS geometry.cgp.v1
   → consumers: Hyperdimensions viewer (Three.js) · a2ui-renderer (Remotion) · WS-B
```

## 7. Scientific contract
- **Reproducible:** pinned model revisions + feature params (sr, hop, n_mels); same audio → identical fingerprint hash (CI-checked).
- **Validated:** silhouette reported per grouping; threshold gate; low → flagged, never invented.
- **Auditable / provable:** CGP v2 `attribution` (Dirichlet + Merkle) + `sig` → every packet traces to model versions + signed provenance; `context_id` for P7 session tracing.
- **Open:** all tools/models permissive.

## 8. Error handling
- `clap-embed` down → librosa-only fallback (degraded, **flagged** in `meta.grounding="partial"`, never silent).
- corrupt/unreadable audio → skip track, log reason, continue.
- silhouette < threshold → flag low-confidence grouping; optional single semantic-tier escalation; do not fabricate clusters.
- schema validation failure → reject packet, log, do not publish.

## 9. Testing
- **Unit:** librosa features deterministic; CLAP embed shape/stability (cosine self-distance ≈ 0); HSV/feature transforms; Poincaré encoder (|z|<1, hierarchy parent links).
- **Integration:** 3 gallery tracks → distinct embeddings (pairwise cosine > τ), clustering separates them, emitted packet **validates against `cgp.v2.schema.json`** with populated hyperbolic/attribution/sig.
- **Service:** `clap-embed` /healthz, embed roundtrip, CPU-fallback path, NATS responder.
- **Reproducibility:** same audio twice → identical fingerprint hash; CGP `sig` verifies.

## 10. Out of scope (other sub-projects)
- WS-B: how the `hyperbolic`/`spectrum` fields render to *visible* surface geometry+color per cluster (consumes WS-A output).
- WS-C/D: viewer gallery + Remotion baked posters. WS-E: Pinokio packaging (promote `pmoves-cipher-beats`/`pmoves-holographic-blocks` SKILL-specs to real launchers; multi-arch `torch.js`; **CHIT-bump the pre-CHIT Jellyfin docs**).

## 11. Decisions & remaining open items
**Resolved (2026-06-03):**
- `clap-embed` **port 8112** in the AI/CHIT tier (verify free at impl).
- Semantic tier: **both** Qwen2-Audio + Step-Audio-2-mini available, **config/registry-driven, not hardcoded**.
- **AST included** in WS-A v1, **model-pluggable** (NVIDIA variants on SPARK GB10 via capacity-class routing).

**Remaining (impl-time):**
- Exact CLAP clip length/hop value (default 10s/mean-pool — confirm against track lengths).
- CHIT signing `kid` / key path — reuse existing CHIT signer (`pmoves-chit-sign`).
- Confirm `clap-embed` port not taken in `.claude/CATALOG.md`.
