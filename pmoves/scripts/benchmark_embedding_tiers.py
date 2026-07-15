#!/usr/bin/env python3
"""
PMOVES Multi-Tier Embedding Benchmark — Phase A

Compares BGE-M3 hybrid (dense + BM25 sparse → RRF) vs Qwen3-4B dense-only
on a representative PMOVES corpus. Outputs recall@10, MRR, and latency.

Usage:
  python3 pmoves/scripts/benchmark_embedding_tiers.py [--qdrant URL] [--tensorzero URL]

Prerequisites:
  - Qdrant running and reachable
  - TensorZero running with bge_m3_local + qwen3_embedding_4b_local configured
  - Ollama with bge-m3 + qwen3-embedding:4b models pulled

Creates three Qdrant collections:
  - pmoves_bench_qwen3   (2560d dense only)
  - pmoves_bench_bge_m3  (1024d dense only)
  - pmoves_bench_hybrid  (1024d dense + bm25 sparse, hybrid RRF)

Then runs a fixed query set and reports recall/MRR/latency for each.
"""
from __future__ import annotations

import argparse
import json
import time
import urllib.request
import urllib.error
import sys
from dataclasses import dataclass, field

# --- Representative PMOVES corpus ---
# Mix of categories: code patterns, decisions, architecture, identifiers,
# natural language. Designed to exercise both semantic and keyword paths.
CORPUS = [
    # Identifiers / exact-match (BM25 should dominate)
    {"id": "c1", "text": "AGNOTE4482 is the multi-agent convergence gateway for PMOVES.AI.", "category": "decision"},
    {"id": "c2", "text": "cipher.memory.stored.v1 NATS subject is published after POST /api/memory.", "category": "code_pattern"},
    {"id": "c3", "text": "PR #2117 merged the Qdrant embedding sidecar for cipher.", "category": "decision"},
    {"id": "c4", "text": "QDRANT_RECREATE_ON_DIM_MISMATCH must be false in production.", "category": "code_pattern"},
    {"id": "c5", "text": "TensorZero gateway listens on port 3030 with ClickHouse observability.", "category": "architecture"},
    # Semantic / paraphrased (dense should dominate)
    {"id": "c6", "text": "The Three-Body Solution separates execution, governance, and memory concerns across agent roles.", "category": "architecture"},
    {"id": "c7", "text": "Agent memory should persist across sessions so context isn't lost on restart.", "category": "decision"},
    {"id": "c8", "text": "Hybrid search combines semantic similarity with keyword matching for better recall.", "category": "architecture"},
    {"id": "c9", "text": "The embedding sidecar falls back to Ollama when TensorZero is unreachable.", "category": "code_pattern"},
    {"id": "c10", "text": "Fail-open design means memory operations never crash due to infrastructure being down.", "category": "architecture"},
    # Mixed (both paths should contribute)
    {"id": "c11", "text": "BGE-M3 model produces 1024-dimensional dense vectors and sparse BM25 representations.", "category": "architecture"},
    {"id": "c12", "text": "RRF fusion with k=60 merges dense and sparse prefetch results.", "category": "code_pattern"},
    {"id": "c13", "text": "The MOF architecture treats every node as a pore in the lattice, not an expertise silo.", "category": "architecture"},
    {"id": "c14", "text": "CHIT signs geometry bus packets on the agent graphiti trail, not memory stores.", "category": "decision"},
    {"id": "c15", "text": "Qwen3-Embedding-4B outputs 2560-dimensional vectors for semantic search.", "category": "code_pattern"},
]

# Query set with expected relevant doc IDs (ground truth)
QUERIES = [
    # Exact-keyword queries (BM25-favoring)
    {"q": "AGNOTE4482", "relevant": ["c1"]},
    {"q": "cipher.memory.stored.v1", "relevant": ["c2"]},
    {"q": "QDRANT_RECREATE_ON_DIM_MISMATCH", "relevant": ["c4"]},
    {"q": "port 3030", "relevant": ["c5"]},
    {"q": "PR #2117", "relevant": ["c3"]},
    # Semantic queries (dense-favoring)
    {"q": "how does agent memory survive restarts", "relevant": ["c7", "c10"]},
    {"q": "what is the three-body agent pattern", "relevant": ["c6"]},
    {"q": "combining keyword and semantic search", "relevant": ["c8", "c12"]},
    {"q": "graceful degradation when services are down", "relevant": ["c9", "c10"]},
    # Mixed queries
    {"q": "BGE-M3 embedding dimensions", "relevant": ["c11", "c15"]},
    {"q": "RRF fusion k parameter", "relevant": ["c12"]},
    {"q": "CHIT signing geometry bus", "relevant": ["c14"]},
]


@dataclass
class BenchmarkResult:
    collection: str
    recall_at_10: float
    mrr: float
    avg_latency_ms: float
    per_query: list = field(default_factory=list)


def tz_embed(tensorzero_url: str, model: str, text: str, timeout: int = 60) -> list[float]:
    """Embed text via TensorZero. Returns dense vector."""
    data = json.dumps({"model": f"tensorzero::embedding_model_name::{model}", "input": text}).encode()
    req = urllib.request.Request(
        f"{tensorzero_url}/openai/v1/embeddings",
        data=data,
        headers={"Content-Type": "application/json"},
    )
    r = urllib.request.urlopen(req, timeout=timeout)
    d = json.loads(r.read())
    return d["data"][0]["embedding"]


def qdrant_call(qdrant_url: str, method: str, path: str, body: dict | None = None) -> dict:
    url = f"{qdrant_url}{path}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
    try:
        r = urllib.request.urlopen(req, timeout=30)
        return json.loads(r.read())
    except urllib.error.HTTPError as e:
        return {"error": e.code, "body": e.read().decode()}


def create_dense_collection(qdrant_url: str, name: str, dim: int):
    """Create a dense-only collection."""
    qdrant_call(qdrant_url, "DELETE", f"/collections/{name}")
    qdrant_call(qdrant_url, "PUT", f"/collections/{name}", {
        "vectors": {"size": dim, "distance": "Cosine"},
    })


def create_hybrid_collection(qdrant_url: str, name: str, dim: int):
    """Create a collection with named dense + BM25 sparse."""
    qdrant_call(qdrant_url, "DELETE", f"/collections/{name}")
    qdrant_call(qdrant_url, "PUT", f"/collections/{name}", {
        "vectors": {"dense": {"size": dim, "distance": "Cosine"}},
        "sparse_vectors": {"bm25": {"modifier": "idf"}},
    })


def upsert_dense(qdrant_url: str, collection: str, points: list[dict]):
    """Upsert points with unnamed dense vectors."""
    qdrant_call(qdrant_url, "PUT", f"/collections/{collection}/points?wait=true", {"points": points})


def upsert_hybrid(qdrant_url: str, collection: str, points: list[dict]):
    """Upsert points with named dense + BM25 sparse."""
    qdrant_call(qdrant_url, "PUT", f"/collections/{collection}/points?wait=true", {"points": points})


def search_dense(qdrant_url: str, collection: str, vector: list[float], limit: int = 10) -> list[dict]:
    """Dense-only search."""
    r = qdrant_call(qdrant_url, "POST", f"/collections/{collection}/points/search", {
        "vector": vector,
        "limit": limit,
        "with_payload": True,
    })
    return r.get("result", [])


def search_hybrid(qdrant_url: str, collection: str, vector: list[float], query_text: str, limit: int = 10) -> list[dict]:
    """Hybrid search: dense + BM25 sparse → RRF."""
    r = qdrant_call(qdrant_url, "POST", f"/collections/{collection}/points/query", {
        "prefetch": [
            {"query": vector, "using": "dense", "limit": limit * 3},
            {"query": {"text": query_text, "model": "qdrant/bm25"}, "using": "bm25", "limit": limit * 3},
        ],
        "fusion": {"rrf": {"k": 60}},
        "limit": limit,
        "with_payload": True,
    })
    return r.get("result", {}).get("points", [])


def recall_at_k(retrieved_ids: list[str], relevant_ids: list[str], k: int = 10) -> float:
    """Fraction of relevant docs in top-k."""
    top_k = retrieved_ids[:k]
    hits = sum(1 for rid in relevant_ids if rid in top_k)
    return hits / len(relevant_ids) if relevant_ids else 0.0


def mrr(retrieved_ids: list[str], relevant_ids: list[str]) -> float:
    """Mean Reciprocal Rank. 1/rank of first relevant doc, 0 if none."""
    for i, rid in enumerate(retrieved_ids, 1):
        if rid in relevant_ids:
            return 1.0 / i
    return 0.0


def run_benchmark(
    qdrant_url: str,
    tensorzero_url: str,
    label: str,
    collection: str,
    embed_model: str,
    embed_dim: int,
    mode: str,  # "dense" or "hybrid"
) -> BenchmarkResult:
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"  collection={collection}  model={embed_model}  dim={embed_dim}  mode={mode}")
    print(f"{'='*60}")

    # Create collection
    if mode == "hybrid":
        create_hybrid_collection(qdrant_url, collection, embed_dim)
    else:
        create_dense_collection(qdrant_url, collection, embed_dim)
    print(f"  ✓ collection created")

    # Embed + upsert corpus
    print(f"  embedding {len(CORPUS)} docs...", end=" ", flush=True)
    points = []
    for doc in CORPUS:
        vec = tz_embed(tensorzero_url, embed_model, doc["text"])
        point = {
            "id": doc["id"],
            "payload": {"text": doc["text"], "category": doc["category"], "doc_id": doc["id"]},
        }
        if mode == "hybrid":
            point["vector"] = {
                "dense": vec,
                "bm25": {"text": doc["text"], "model": "qdrant/bm25"},
            }
        else:
            point["vector"] = vec
        points.append(point)
    upsert_dense(qdrant_url, collection, points) if mode != "hybrid" else upsert_hybrid(qdrant_url, collection, points)
    print("done")

    # Run queries
    recalls = []
    mrrs = []
    latencies = []
    per_query = []

    for qi, q in enumerate(QUERIES):
        q_vec = tz_embed(tensorzero_url, embed_model, q["q"])

        t0 = time.perf_counter()
        if mode == "hybrid":
            hits = search_hybrid(qdrant_url, collection, q_vec, q["q"])
        else:
            hits = search_dense(qdrant_url, collection, q_vec)
        latency_ms = (time.perf_counter() - t0) * 1000

        retrieved = [h.get("payload", {}).get("doc_id", str(h.get("id", ""))) for h in hits]
        rel = q["relevant"]
        r10 = recall_at_k(retrieved, rel)
        rr = mrr(retrieved, rel)

        recalls.append(r10)
        mrrs.append(rr)
        latencies.append(latency_ms)
        per_query.append({
            "q": q["q"], "relevant": rel, "retrieved": retrieved[:5],
            "recall@10": r10, "rr": rr, "latency_ms": round(latency_ms, 1),
        })
        status = "✓" if r10 > 0 else "✗"
        print(f"  {status} q{qi+1:2d} [{latency_ms:6.1f}ms] recall={r10:.2f} mrr={rr:.2f}  \"{q['q'][:50]}\"")

    result = BenchmarkResult(
        collection=collection,
        recall_at_10=sum(recalls) / len(recalls),
        mrr=sum(mrrs) / len(mrrs),
        avg_latency_ms=sum(latencies) / len(latencies),
        per_query=per_query,
    )
    print(f"\n  SUMMARY: recall@10={result.recall_at_10:.3f}  MRR={result.mrr:.3f}  avg_latency={result.avg_latency_ms:.1f}ms")
    return result


def main():
    parser = argparse.ArgumentParser(description="PMOVES multi-tier embedding benchmark")
    parser.add_argument("--qdrant", default="http://localhost:6333", help="Qdrant URL")
    parser.add_argument("--tensorzero", default="http://localhost:3030", help="TensorZero URL")
    parser.add_argument("--skip-qwen3", action="store_true", help="Skip Qwen3-4B (slow on first embed)")
    args = parser.parse_args()

    # Preflight checks
    print("Preflight: checking services...")
    try:
        tz_embed(args.tensorzero, "bge_m3_local", "warmup", timeout=120)
        print("  ✓ BGE-M3 via TensorZero")
    except Exception as e:
        print(f"  ✗ BGE-M3 via TensorZero: {e}")
        sys.exit(1)

    if not args.skip_qwen3:
        try:
            tz_embed(args.tensorzero, "qwen3_embedding_4b_local", "warmup", timeout=120)
            print("  ✓ Qwen3-4B via TensorZero")
        except Exception as e:
            print(f"  ✗ Qwen3-4B via TensorZero: {e}")
            print("  (run with --skip-qwen3 to benchmark BGE-M3 only)")

    try:
        qdrant_call(args.qdrant, "GET", "/collections")
        print("  ✓ Qdrant")
    except Exception as e:
        print(f"  ✗ Qdrant: {e}")
        sys.exit(1)

    results = []

    # Benchmark 1: Qwen3-4B dense-only (current PMOVES default)
    if not args.skip_qwen3:
        results.append(run_benchmark(
            args.qdrant, args.tensorzero,
            "Qwen3-4B Dense-Only (CURRENT DEFAULT)", "pmoves_bench_qwen3",
            "qwen3_embedding_4b_local", 2560, "dense",
        ))

    # Benchmark 2: BGE-M3 dense-only
    results.append(run_benchmark(
        args.qdrant, args.tensorzero,
        "BGE-M3 Dense-Only", "pmoves_bench_bge_m3",
        "bge_m3_local", 1024, "dense",
    ))

    # Benchmark 3: BGE-M3 hybrid (dense + BM25 → RRF) — THE PROPOSAL
    results.append(run_benchmark(
        args.qdrant, args.tensorzero,
        "BGE-M3 Hybrid (dense + BM25 → RRF) — PROPOSAL", "pmoves_bench_hybrid",
        "bge_m3_local", 1024, "hybrid",
    ))

    # Final comparison table
    print(f"\n{'='*70}")
    print("  FINAL COMPARISON")
    print(f"{'='*70}")
    print(f"  {'Configuration':<45} {'Recall@10':>10} {'MRR':>8} {'Latency':>10}")
    print(f"  {'-'*45} {'-'*10} {'-'*8} {'-'*10}")
    for r in results:
        print(f"  {r.collection:<45} {r.recall_at_10:>10.3f} {r.mrr:>8.3f} {r.avg_latency_ms:>8.1f}ms")
    print()

    # Save JSON
    out_path = "pmoves_bench_embedding_tiers_results.json"
    with open(out_path, "w") as f:
        json.dump({
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "corpus_size": len(CORPUS),
            "query_count": len(QUERIES),
            "results": [
                {
                    "collection": r.collection,
                    "recall_at_10": r.recall_at_10,
                    "mrr": r.mrr,
                    "avg_latency_ms": r.avg_latency_ms,
                    "per_query": r.per_query,
                }
                for r in results
            ],
        }, f, indent=2)
    print(f"Results saved to {out_path}")


if __name__ == "__main__":
    main()
