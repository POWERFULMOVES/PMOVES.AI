# PMOVES Longbow — Deprecated

**Status:** Deprecated
**Date:** 2026-07-30
**Decision:** Longbow is documentation-only, never integrated. Qdrant + Meilisearch serve as the de facto vector + lexical layers.

## Context

Longbow was an external Go-based vector database (HNSW + BM25 + hybrid + GraphRAG, Arrow Flight, SlabArena) evaluated in `research/LONGBOW_COMPARATIVE_ANALYSIS.md` as a candidate for PMOVES's "vector memory layer."

## Why Deprecated

Per `pmoves/docs/TAC/TAC_CIPHER.md:402`: *"LongBow is documentation-only — never integrated. Qdrant (:6333) is the de facto vector layer today."*

The BM25/hybrid retrieval capability that Longbow was meant to provide is already delivered through two production paths:

1. **Cipher Memory** — Qdrant collection `pmoves_cipher_memory` with dense (2560d COSINE) + BM25 sparse (`modifier: 'idf'`) vectors, fused via RRF (`Pmoves-cipher/src/pmoves/embedding.ts`).
2. **Hi-RAG Gateway v2** — Qdrant dense kNN + Meilisearch full-text lexical + optional Neo4j graph boost, fused via convex-combine `hybrid_score(alpha)` (`pmoves/services/hi-rag-gateway-v2/`).

No PMOVES-Longbow submodule exists in `.gitmodules`. No code was ever written.

## Resolution

This document satisfies the `stage-4.longbow-or-deprecated` launch-readiness gate (`pmoves/configs/tac_trees/pmoves-launch-readiness.tac.yaml:253`) via the deprecation path.
