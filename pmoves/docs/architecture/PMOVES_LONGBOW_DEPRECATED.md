# PMOVES Longbow — Deprecated

**Status:** Deprecated
**Date:** 2026-07-30
**Decision:** Longbow is **not adopted**. Qdrant + Meilisearch serve as the de facto vector + lexical layers.
**Corrected:** 2026-08-06 — the original rationale asserted that no Longbow code was ever written. That was factually wrong; see "Correction" below. The decision stands on the superseded-by-Cipher/Hi-RAG grounds, not on the false premise.

## Context

Longbow was an external Go-based vector database (HNSW + BM25 + hybrid + GraphRAG, Arrow Flight, SlabArena) evaluated in `research/LONGBOW_COMPARATIVE_ANALYSIS.md` as a candidate for PMOVES's "vector memory layer."

## Why Deprecated

The original rationale cited `pmoves/docs/TAC/TAC_CIPHER.md:402`: *"LongBow is documentation-only — never integrated. Qdrant (:6333) is the de facto vector layer today."* That line is dated **2026-07-13** — one day BEFORE the integration work described in "Correction" below. It was true when written and stale by the time it was cited.

The BM25/hybrid retrieval capability that Longbow was meant to provide is already delivered through two production paths:

1. **Cipher Memory** — Qdrant collection `pmoves_cipher_memory` with dense (2560d COSINE) + BM25 sparse (`modifier: 'idf'`) vectors, fused via RRF (`Pmoves-cipher/src/pmoves/embedding.ts`).
2. **Hi-RAG Gateway v2** — Qdrant dense kNN + Meilisearch full-text lexical + optional Neo4j graph boost, fused via convex-combine `hybrid_score(alpha)` (`pmoves/services/hi-rag-gateway-v2/`).

## Correction (2026-08-06) — code WAS written

The statement previously here — *"No PMOVES-Longbow submodule exists in `.gitmodules`. No code was ever written."* — is **false**. Verified against git:

| Commit | Date | Author | What |
|---|---|---|---|
| `294ea52f7` | 2026-07-15 | PMOVES-AGENT-ZERO-SPARK | `feat(submodule): add PMOVES--longbow (Arrow-Flight vector cache)` — real submodule, fork of `23skdu/longbow` (Go, Arrow-Flight, HNSW) |
| `23af4df50` | 2026-07-15 | PMOVES-AGENT-ZERO-SPARK | `feat(longbow): Phase D — compose stanza + profile data wiring` — ports 3100/3101/9190, healthcheck, resource limits, networks, volume |

Both live on `origin/fix/cipher-search-memoryid-followup`, which is **345 commits behind main** with no open PR. The work was never merged — so there is no removal commit either, which is why a search of `main` alone finds nothing.

That branch also carries a benchmarked multi-tier embedding spec (`high` Qwen3-8B 4096d / `medium` BGE-M3 1024d / `low` nomic-embed 768d, plus `bm25`/`bge_sparse` sparse fields) with recall@10 and p50/p99 measured on SPARK GB10 and 4090 hardware.

**How the error happened, and why it matters beyond Longbow:** the closing pass checked `main`'s current state plus one doc line. It did not check git history or unmerged branches. Any automated gate-closure that reads only `main` will miss unmerged work and can write "never existed" into the permanent record. That is a process failure mode, not a Longbow-specific one.

### Naming collision

Two unrelated things share the name, and the original deprecation conflated them:

- **Longbow (vector cache)** — the fork above, positioned as an **L1 hot-path cache in front of Qdrant**, not a replacement for it. Real, benchmarked, unmerged.
- **Longbow (model router)** — a contextual-bandit router between agents and models, described in `pmoves/docs/architecture/LONGBOW_INTEGRATION.md`. Never built; correctly abandoned.

The router was rightly dropped. The vector cache was deprecated by proxy.

## Resolution

This document satisfies the `stage-4.longbow-or-deprecated` launch-readiness gate (`pmoves/configs/tac_trees/pmoves-launch-readiness.tac.yaml:253`) via the deprecation path.
