# PMOVES Multi-Tier Embedding Architecture

> **STATUS:** Design — operator review pending. No code committed.
> **Last refreshed:** 2026-07-14 (CRUSH-GLM52, initial research synthesis).
> **Prereqs:** PR #2119 (cipher search() fix) merged; Hi-RAG v2 healthy; Qdrant :6333 live.

## Motivation

PMOVES currently uses a **single-dimension embedding strategy**: one embedder per Qdrant collection (`pmoves_chunks_qwen3` 2560d for Hi-RAG, `pmoves_cipher_memory` 2560d for cipher). This creates three problems:

1. **No cost-tiering.** Every query pays for a 4B-param embed regardless of whether the query is a cheap cache-hit check or a deep semantic probe.
2. **No hybrid search.** Dense-only retrieval misses exact-keyword matches that BM25/sparse catches (function names, IDs, error strings, exact-phrase quotes).
3. **No graceful degradation.** If TensorZero is down, the Ollama fallback embeds at the SAME dimension — but if the Qdrant collection was built at 2560d and the fallback emits 384d, every search silently fails.

The 3-tier architecture (high / medium / low dim + sparse) solves all three by storing multiple representations of the same document in one Qdrant collection via **named vectors**, then fusing results with **hybrid search (RRF)**.

## Naming collision — disambiguation (READ FIRST)

Two names in this ecosystem collide with existing PMOVES docs. This doc refers ONLY to the actual GitHub repos linked by the operator.

| Name | This doc refers to | NOT the existing PMOVES doc |
|------|-------------------|-----------------------------|
| **Darkmatter** | [`POWERFULMOVES/PMOVES-Darkmatter`](https://github.com/POWERFULMOVES/PMOVES-Darkmatter) — fork of `qdrant/qdrant` v1.18.2 (Rust vector DB) | `DARKMATTER_FACTORY.md` = model-minting pipeline (Unsloth/Pinokio) — **unrelated** |
| **LongBow** | [`POWERFULMOVES/PMOVES--longbow`](https://github.com/POWERFULMOVES/PMOVES--longbow) — fork of `23skdu/longbow` (Arrow-Flight distributed vector cache, Go) | `LONGBOW_INTEGRATION.md` = contextual-bandit model router — **unrelated** |

**Action item:** keep both names — they are apt. Disambiguate by context: "Darkmatter/Qdrant" (the vector DB fork) vs "Darkmatter Factory" (the model minting pipeline). "LongBow" is apt for the vector cache (long-range retrieval) and tongue-in-cheek. Cross-reference the docs so agents landing on either know the other exists.

## Model tier mapping

Research sources: MTEB leaderboard (Oct 2025), Modal embedding guide, HuggingFace model cards. All models below are Apache-2.0 or MIT (commercial-safe).

| Tier | Model | Dim | Params | License | MTEB | Role | Already in PMOVES? |
|------|-------|-----|--------|---------|------|------|---------------------|
| **HIGH** | `Qwen/Qwen3-Embedding-8B` | 4096 | 8B | Apache-2.0 | Top-3 | Deep semantic probe (cold path, RAG over large corpus) | No |
| **HIGH** | `Qwen/Qwen3-Embedding-4B` | 2560 | 4B | Apache-2.0 | Top-5 | **Current default** — cipher sidecar + Hi-RAG `pmoves_chunks_qwen3` | **Yes** |
| **MEDIUM** | `BAAI/bge-m3` | 1024 | 568M | MIT | Strong | **Keystone** — emits dense + sparse + ColBERT from ONE model. Best single-embedder hybrid | No |
| **MEDIUM** | `dunzhang/stella_en_1.5B_v5` | 1024 (Matryoshka) | 1.5B | MIT | Strong | English-only alternative if BGE-M3 underperforms; Matryoshka truncates to 512/256 | No |
| **LOW** | `google/embeddinggemma-300m` | 768 (Matryoshka) | 300M | Apache-2.0 | Good | Hot-path cache-key embed; mobile/edge nodes; cost floor | No |
| **LOW** | `sentence-transformers/all-MiniLM-L6-v2` | 384 | 23M | Apache-2.0 | Legacy | **Current legacy** — `pmoves_chunks` collection, extract-worker default | **Yes** (legacy) |
| **SPARSE** | `BAAI/bge-m3` (sparse mode) | sparse | — | MIT | — | Same model as medium tier — no extra dep if BGE-M3 adopted | Inherits medium |
| **SPARSE** | Qdrant BM25 (built-in) | sparse | — | Apache-2.0 | — | Zero-dep; tokenizes payload text field; no model needed | Qdrant native |

### Why BGE-M3 is the keystone

BGE-M3 emits three outputs from a single forward pass:
1. **Dense** (1024d) — standard semantic similarity
2. **Sparse** (lexical) — BM25-style keyword matching
3. **Multi-vector** (ColBERT) — late-interaction token-level scoring

If PMOVES adopts BGE-M3 as the medium tier, **hybrid search is free** — one embedder call produces both dense and sparse vectors for the same document, and Qdrant fuses them via RRF. No separate sparse model, no double-ingestion.

### Matryoshka representation learning (MRL)

Models marked "Matryoshka" (`stella_en_1.5B_v5`, `embeddinggemma-300m`) produce embeddings that can be **truncated** to lower dimensions without retraining. A 1024d Matryoshka vector truncated to 256d retains ~90% of the retrieval quality. This means:

- One model can serve multiple tiers (1024d for precision, 256d for speed)
- No separate "low" model needed if the medium tier is Matryoshka
- Graceful degradation: if GPU is busy, truncate to 256d and still get usable results

## Target architecture

```
                        ┌─────────────────────────────────┐
   QUERY ──────────────►│  LongBow (L1 cache)             │
                        │  Arrow-Flight :3000/:3001       │
                        │  sub-ms hot path                │
                        └────────────┬────────────────────┘
                                     │ cache miss
                                     ▼
                        ┌─────────────────────────────────┐
                        │  Qdrant (PMOVES-Darkmatter)     │
                        │  collection: pmoves_hybrid      │
                        │                                 │
                        │  named vectors:                 │
                        │    "high"    → 4096d Qwen3-8B   │
                        │    "medium"  → 1024d BGE-M3     │
                        │    "low"     → 768d  Gemma-300M │
                        │                                 │
                        │  sparse vectors:                │
                        │    "bm25"    → Qdrant built-in  │
                        │    "bge_sparse" → BGE-M3 sparse │
                        │                                 │
                        │  HYBRID QUERY:                  │
                        │    prefetch(dense=medium,       │
                        │              sparse=bm25)       │
                        │    → RRF fusion (k=60)          │
                        └─────────────────────────────────┘
```

### Tiered query routing

| Query type | Embedder | Vector field | Latency target |
|-----------|----------|-------------|----------------|
| Cache-key check (semantic-cache Layer 0) | Gemma-300M (low) | `low` | <5ms |
| Standard RAG retrieval | BGE-M3 (medium) + BM25 | `medium` + `bm25` hybrid | <50ms |
| Deep semantic probe (multi-phrasing recall) | Qwen3-8B (high) | `high` | <500ms |
| Exact-keyword match (function names, IDs) | Qdrant BM25 (sparse) | `bm25` | <10ms |

## Qdrant collection schema

Single collection with named vectors + sparse fields. This is the **PMOVES-Darkmatter fork's** configuration surface (standard Qdrant v1.18.2 — no fork modifications needed yet).

```json
{
  "vectors": {
    "high":   { "size": 4096, "distance": "Cosine" },
    "medium": { "size": 1024, "distance": "Cosine" },
    "low":    { "size": 768,  "distance": "Cosine" }
  },
  "sparse_vectors": {
    "bm25":       {},
    "bge_sparse": {}
  }
}
```

### Hybrid query example (RRF fusion)

```json
{
  "prefetch": [
    {
      "query": "<bge_m3_dense_vector>",
      "using": "medium",
      "limit": 20
    },
    {
      "query": "<bm25_sparse_vector>",
      "using": "bm25",
      "limit": 20
    }
  ],
  "fusion": { "rrf": { "k": 60 } },
  "limit": 10
}
```

### Ingestion contract

Every document upserted to `pmoves_hybrid` MUST include:
- `medium` vector (BGE-M3 dense) — **required** (primary retrieval tier)
- `bm25` sparse (Qdrant tokenizes the `text` payload field) — **required** (keyword recall)
- `high` vector (Qwen3-8B) — **optional** (only for documents flagged "deep-probe")
- `low` vector (Gemma-300M) — **optional** (only for documents in the semantic-cache hot path)
- `bge_sparse` (BGE-M3 sparse) — **optional** (better than BM25 for OOV terms, but needs the model)

This means ingestion cost scales with tier participation — not every doc needs all 4 vectors.

## LongBow integration (L1 cache)

**Current state:** `PMOVES--longbow` fork is v0.1.9-rc5, **2 months behind upstream** (`23skdu/longbow` at v0.2.2-rc1). Zero PMOVES customizations.

**Role in this architecture:** sub-ms vector cache in front of Qdrant for hot queries (semantic-cache Layer 0, repeated RAG lookups, agent memory recall loops). Qdrant stays the persistent source of truth; LongBow holds hot vectors in RAM as zero-copy Arrow buffers.

**Rebase plan:**
1. Fetch upstream: `git fetch upstream && git log --oneline main..upstream/main` (expect ~2 months of commits)
2. Rebase: `git rebase upstream/main` (fork is pristine, expect clean fast-forward)
3. Verify build: `cargo build --release` (Go workspace, not Rust — `go build ./cmd/longbow`)
4. Tag: `v0.2.2-pmoves.1` (first PMOVES-aware tag, even if no customizations, for fleet tracking)
5. Add as submodule: `PMOVES--longbow` → `.gitmodules` tracking `main`

**Upstream additions since fork (relevant to PMOVES):**
- GPU OOM fixes + CUDA memory pool routing (5090/SPARK)
- AVX2/AVX-512 int32/uint32 dot+euclidean kernels (Z890/Knuckles CPU path)
- AMX assembly kernels (Intel Emerald/Granite Rapids)
- TurboQuant at-scale optimizations
- Serialization corruption bug fix (data durability)
- LockFreeNeighborCache (HNSW concurrency)

**Decision needed:** Does LongBow replace the cipher semantic-cache Layer 0, or sit alongside it?
- **Replace:** LongBow sub-ms cache supersedes the cipher `/api/memory/search` pre-check
- **Alongside:** Cipher handles agent-memory recall; LongBow handles document-RAG hot path
- **Recommendation:** Alongside — different data domains (agent memory vs documents)

## PMOVES-Darkmatter (Qdrant fork) integration

**Current state:** fork is identical to upstream `qdrant/qdrant@1.18.2`. Zero modifications.

**What this fork enables (future, not this phase):**
- Custom HNSW tuning for PMOVES workload patterns (agent memory recall vs document RAG have different access patterns)
- Native CGP-geometry-aware distance metrics (if CHIT geometry bus needs custom similarity)
- Embedded mode (Qdrant Edge) for island-mode nodes (4090 laptop, SPARK offline)
- Custom sparse tokenizer for PMOVES identifier conventions (`AGNOTE4482`, `cipher.memory.stored.v1`, etc.)

**This phase (no fork modifications needed):** Qdrant v1.18.2 stock supports everything in the target architecture. The fork exists as the **customization surface** for when PMOVES outgrows stock config.

**Config file location:** fork's `config/config.yaml` is the canonical place for PMOVES-specific HNSW/optimizer defaults. Current stock values are fine; future tuning lands here.

## Migration plan (phased)

### Phase A — BGE-M3 medium tier (unblocks hybrid search) ✅ BENCHMARKED

**Benchmark results (live, Qdrant 1.16.0, SPARK node):**

| Config | Recall@10 | MRR | Avg Latency |
|--------|----------|-----|-------------|
| BGE-M3 Dense-Only (1024d) | **1.000** | **1.000** | 1.5ms |
| BGE-M3 Hybrid (dense + BM25 → RRF) | **1.000** | **1.000** | 1.8ms |

Both achieve perfect recall on the 15-doc test corpus. Hybrid adds ~0.3ms for BM25 prefetch + RRF fusion. The BM25 sparse path correctly matched exact PMOVES identifiers (AGNOTE4482, NATS subjects, PR numbers). The `qdrant/bm25` server-side tokenizer works natively — no external sparse model needed.

**Qdrant version note:** Running Qdrant is v1.16.0 (not 1.18.2 as PMOVES-Darkmatter fork). In v1.16, hybrid fusion goes in the top-level `query` field as `{"fusion": "rrf"}`, not as a `fusion` sibling key.

- [x] Add `BAAI/bge-m3` to TensorZero config (`tensorzero.toml`) as `bge_m3_local`
- [x] Pull model: `ollama pull bge-m3` (1.2GB, verified 1024d)
- [x] Create `pmoves_hybrid` collection with `medium` (1024d) + `bm25` (sparse) named vectors — benchmarked via `pmoves_bench_hybrid`
- [x] Benchmark: BGE-M3 hybrid vs BGE-M3 dense-only — both 1.000 recall on test corpus
- [ ] Update extract-worker to emit BGE-M3 dense + sparse on ingest — deferred to production integration
- [ ] Update Hi-RAG v2 query path to use hybrid prefetch — deferred to Hi-RAG integration

### Phase B — Low tier (semantic-cache acceleration) ✅ BENCHMARKED

**Benchmark results (warm, 20 iterations, 4090 laptop):**

| Model | Dim | Params | p50 Embed | p99 Embed | Role |
|-------|-----|--------|-----------|-----------|------|
| **nomic-embed-text** | 768 | 137M | **25.7ms** | 798ms | **LOW tier winner** — 5× faster than gemma |
| embeddinggemma-300m | 768 | 300M | 125ms | 154ms | Alternative (more stable p99) |
| BGE-M3 | 1024 | 568M | 192.8ms | 225ms | MEDIUM tier (Phase A) |

**Finding:** nomic-embed-text (137M) is the clear low-tier winner for cache-key embedding — 5× faster than gemma-300m and 7× faster than BGE-M3. It's already pulled on all nodes and registered in TensorZero as `archon_nomic_embed_local`. Use nomic-embed-text when latency matters more than precision (cache-key check, hot-path dedup); use BGE-M3 when recall quality matters (RAG retrieval).

- [x] Add `google/embeddinggemma-300m` to TensorZero config — already registered as `gemma_embed_local`
- [x] Add `nomic-embed-text` to TensorZero config — already registered as `archon_nomic_embed_local`
- [x] Benchmark: low-tier embed latency (nomic 25ms p50 vs gemma 125ms vs BGE-M3 192ms)
- [ ] Add `low` (768d) named vector to `pmoves_hybrid` collection — deferred to Phase D integration
- [ ] Wire cipher semantic-cache Layer 0 to use `low` tier (nomic) — deferred to cipher integration

### Phase C — High tier (deep probe) ✅ BENCHMARKED

**3-tier benchmark (warm, SPARK GB10 node, 128GB unified memory):**

| Tier | Model | Dim | Recall@10 | Embed p50 | Search p50 | Total p50 |
|------|-------|-----|----------|-----------|------------|-----------|
| **LOW** | nomic-embed-text | 768 | 1.000 | **30.3ms** | 1.5ms | **31.8ms** |
| **MEDIUM** | BGE-M3 | 1024 | 1.000 | 207.9ms | 1.7ms | 209.7ms |
| **HIGH** | Qwen3-Embedding-8B | 4096 | 1.000 | 159.2ms | 2.9ms | 162.2ms |

**Key findings:**
1. **All tiers achieve perfect recall** on the 15-doc corpus — the corpus is small enough that quality differences need a larger dataset to surface.
2. **LOW tier (nomic) is 5-7× faster** for embedding than medium/high — ideal for cache-key checks.
3. **HIGH tier (Qwen3-8B) is surprisingly fast** — 159ms embed vs BGE-M3's 207ms. The GB10's unified memory likely helps (no PCIe bottleneck). Search is slightly slower (2.9ms vs 1.7ms) due to 4096d vectors.
4. **BGE-M3 remains the keystone for hybrid** — it's the only model that emits dense + sparse in one call. HIGH and LOW tiers are dense-only.

**Tier routing (per-data-type, not global):**
| Data type | Tier | Rationale |
|-----------|------|-----------|
| Cache-key dedup (semantic-cache Layer 0) | LOW (nomic) | Speed-critical, 30ms embed |
| RAG retrieval (documents, transcripts) | MEDIUM (BGE-M3 hybrid) | Best recall + keyword matching |
| Deep semantic probe (multi-phrasing recall) | HIGH (Qwen3-8B) | Max precision for complex queries |
| Agent memory (cipher) | MEDIUM (BGE-M3 hybrid) | Same as RAG — BM25 catches exact identifiers |
| Code identifiers, NATS subjects | BM25 sparse (Qdrant built-in) | Exact match, no model needed |

- [x] Add `Qwen/Qwen3-Embedding-8B` to TensorZero config — already registered as `qwen3_embedding_8b_local`
- [x] Pull model: `ollama pull qwen3-embedding:8b` (4.7GB, verified 4096d)
- [x] Benchmark: recall@10 on high-tier (1.000, same as low/medium on this corpus)
- [ ] Add `high` (4096d) named vector to `pmoves_hybrid` collection — deferred to Phase D integration
- [ ] Wire Hi-RAG `/hirag/query?deep=true` to use `high` tier — deferred to Hi-RAG integration

### Phase D — LongBow cache layer ✅ COMPOSE-WIRED

- [x] Rebase `PMOVES--longbow` onto upstream `23skdu/longbow@main` — done (synced to `9b1dc5be`, ARM64 AMX stub fix `0b0c4487`)
- [x] Tag `v0.2.2-pmoves.1`, add as submodule — done (commit `294ea52f7`)
- [x] Compose stanza: LongBow in `docker-compose.yml` (profile `data`), host ports `3100`/`3101`/`9190` (mapped from container `3000`/`3001`/`9090` to avoid PMOVES port conflicts), `pmoves_data` + `pmoves_api` networks, `longbow-data` volume, hardened anchor (`x-tier-data-hardened`)
- [ ] Wire Hi-RAG to check LongBow before Qdrant — deferred to Hi-RAG integration
- [ ] Benchmark: p99 latency with/without cache — deferred to live bring-up

### Phase E — PMOVES-Darkmatter customization (future)
- [ ] Profile HNSW access patterns (agent memory vs document RAG)
- [ ] Tune `config/config.yaml` HNSW M / ef_construct for PMOVES workload
- [ ] Evaluate custom sparse tokenizer for PMOVES identifier conventions
- [ ] Evaluate Qdrant Edge (embedded) for island-mode nodes

## Cipher sidecar — Qdrant BM25 replaces ByteRover MiniSearch

The new Cipher (ByteRover v3.16.1) ships with an in-memory MiniSearch BM25 index (`src/agent/infra/swarm/search-precision.ts`, `memory-wiki-adapter.ts`). MiniSearch is capped at ~10K entries before sharding is needed. The A1-Shim added a Qdrant dense-vector sidecar (`pmoves_cipher_memory`) but left ByteRover's MiniSearch as the lexical backend.

**Upgrade:** add a Qdrant BM25 sparse field to `pmoves_cipher_memory`. This gives cipher **hybrid search** (dense semantic + sparse keyword → RRF) at any scale, and eliminates the MiniSearch 10K ceiling.

### Current cipher sidecar collection (dense-only)

```json
// embedding.ts ensureCollection() — current
{
  "vectors": {"size": 2560, "distance": "Cosine"}
}
```

### Target cipher sidecar collection (hybrid)

```json
// embedding.ts ensureCollection() — target
{
  "vectors": {"size": 2560, "distance": "Cosine"},
  "sparse_vectors": {"bm25": {}}
}
```

Qdrant's built-in BM25 tokenizes a payload text field automatically — no model needed, no extra embedder call. The cipher sidecar just needs to include the memory `content` in the point payload so BM25 can index it.

### Cipher sidecar code changes (3 methods in `embedding.ts`)

**1. `ensureCollection()` — add sparse field:**
```typescript
body: JSON.stringify({
  vectors: {size: this.embeddingDim, distance: 'Cosine'},
  sparse_vectors: {bm25: {}},  // ← NEW: Qdrant built-in BM25
}),
```

**2. `storeVector()` — include content in payload for BM25 tokenization:**
```typescript
points: [{
  id: pointId,
  vector: embedding.vector,
  payload: {memoryId, category, tags, content},  // ← content added
}],
```
Currently the sidecar stores `{memoryId, category, tags}` — BM25 needs the raw text. Adding `content` to payload lets Qdrant's BM25 tokenizer index it automatically when the sparse field is configured.

**3. `search()` — switch to hybrid query (dense + sparse → RRF):**
```typescript
// Current: dense-only /points/search
// Target: /points/query with prefetch + fusion
body: JSON.stringify({
  prefetch: [
    {query: queryEmbedding.vector, using: null, limit: limit * 2},  // dense
    {query: {scroll: {filter: ...}}, using: "bm25", limit: limit * 2},  // sparse
  ],
  fusion: {rrf: {k: 60}},
  limit,
  with_payload: true,
})
```
Note: Qdrant sparse queries take a text query (not a vector) — the sparse path uses the raw query string, Qdrant tokenizes it internally. This means `search()` needs both the embedding AND the raw query text (the caller in `memory-routes.ts:49` has `q` available — just pass it through).

### Why this matters for cipher

| Dimension | MiniSearch (ByteRover native) | Qdrant BM25 (sidecar upgrade) |
|-----------|-------------------------------|-------------------------------|
| Scale limit | ~10K entries (in-memory) | Unlimited (disk-backed) |
| Hybrid search | No (BM25-only) | Yes (dense + sparse → RRF) |
| Persistence | None (rebuilt on restart) | Persistent (Qdrant collection) |
| Cross-collection | No | Yes (can fan out to `pmoves_hybrid`) |
| Memory cost | Full index in RAM | Only HNSW graph in RAM |
| PMOVES identifier matching | Generic tokenizer | Same — but can be tuned via fork |

### Parallel to LongBow

The user's insight: "the new cipher was in the same state as longbow." Both are **pristine upstream** with PMOVES customizations as an additive layer:
- **LongBow** (Arrow-Flight cache): pristine `23skdu/longbow` fork, no PMOVES code → we shape it as the L1 cache
- **Cipher** (ByteRover): pristine upstream after A1-Shim re-fork, PMOVES shim is additive → we shape it to use Qdrant BM25 instead of MiniSearch

Both are "clean slate" — we can integrate them with the Qdrant multi-tier architecture from the start rather than retrofitting later.

- **`pmoves_chunks_qwen3` (2560d Qwen3-4B):** stays as-is for Hi-RAG document retrieval until Phase A benchmarks prove BGE-M3 hybrid is better. No forced migration.
- **`pmoves_chunks` (384d MiniLM):** stays as legacy. New ingestion goes to `pmoves_hybrid`. Gradual sunset.
- **`pmoves_cipher_memory` (2560d cipher sidecar):** independent — cipher keeps its own collection. The multi-tier architecture is for Hi-RAG / extract-worker / document RAG, not agent episodic memory.

## Open questions for operator

1. **BGE-M3 vs Qwen3-4B for medium tier:** Benchmark in Phase A. Different embeddings will be used for different data types — tier selection is per-data-type, not global. → Map data types to tiers after benchmark.
2. **LongBow scope:** Replace cipher semantic-cache Layer 0, or sit alongside for document-RAG only? → Recommendation: alongside.
3. **Fork naming:** Keep both names. "Darkmatter" is apt (model minting factory + the Qdrant fork both earn the name). "LongBow" is apt + tongue-in-cheek. No rename. Disambiguation handled by context ("Darkmatter/Qdrant" vs "Darkmatter Factory").
4. **Qwen3-8B hosting:** Any capable node — not restricted to 5090/SPARK. Any node with sufficient VRAM can host the high tier.
5. **Matryoshka truncation:** If BGE-M3 medium tier (1024d) is Matryoshka-trained, can we skip the separate low tier and just truncate to 256d for cache keys? → Verify BGE-M3 Matryoshka support.
6. **Cipher BM25 upgrade:** Investigate cipher code path first, then decide whether to fold into PR #2119 follow-up or separate lane.

## References

- [MTEB Leaderboard](https://huggingface.co/spaces/mteb/leaderboard)
- [Modal: Top MTEB models (Oct 2025)](https://modal.com/blog/mteb-leaderboard-article)
- [Qwen3-Embedding-8B](https://huggingface.co/Qwen/Qwen3-Embedding-8B)
- [BGE-M3](https://huggingface.co/BAAI/bge-m3)
- [embeddinggemma-300m](https://huggingface.co/google/embeddinggemma-300m)
- [stella_en_1.5B_v5](https://huggingface.co/dunzhang/stella_en_1.5B_v5)
- [Qdrant hybrid search docs](https://qdrant.tech/articles/hybrid-search/)
- [Qdrant named vectors](https://qdrant.tech/documentation/concepts/collections/#collection-with-multiple-vectors)
- [Matryoshka representation learning](https://huggingface.co/blog/matryoshka)
- Existing PMOVES docs: `TAC_EMBEDDING_PIPELINE.md` (stale — single-tier), `LONGBOW_INTEGRATION.md` (different concept — model router), `DARKMATTER_FACTORY.md` (different concept — model minting)

<!-- GRAPHITI_MARK: CRUSH-GLM52::MULTI-TIER-EMBEDDING-ARCH-SPEC::2026-07-14 -->
