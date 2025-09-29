from __future__ import annotations

import argparse
import csv
import json
import math
import os
from pathlib import Path
from typing import Any, Dict, List, Tuple

import requests

from eval_utils import (
    artifact_metadata,
    ensure_directory,
    evaluate_suites,
    group_suites_by_type,
    load_json,
    utc_now,
)


def dcg(scores: List[float]) -> float:
    return sum((s / math.log2(i + 2)) for i, s in enumerate(scores))


def ndcg_at_k(rels: List[int], k: int) -> float:
    gains = [1.0 if r else 0.0 for r in rels[:k]]
    idcg = dcg(sorted(gains, reverse=True))
    return (dcg(gains) / idcg) if idcg > 0 else 0.0


def mrr_at_k(rels: List[int], k: int) -> float:
    for i, r in enumerate(rels[:k]):
        if r:
            return 1.0 / (i + 1)
    return 0.0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate retrieval quality via MRR/NDCG and optional bias/stress suites.",
    )
    parser.add_argument("queries", help="Path to JSONL file of evaluation queries.")
    parser.add_argument("--k", type=int, default=int(os.environ.get("EVAL_K", "10")))
    parser.add_argument(
        "--hirag-url",
        default=os.environ.get("HIRAG_URL", "http://hi-rag-gateway-v2:8086"),
        help="hi-RAG gateway URL (default from HIRAG_URL).",
    )
    parser.add_argument("--timeout", type=float, default=30.0, help="Request timeout in seconds.")
    parser.add_argument("--suites", help="Optional path to a suites JSON file for bias/stress evaluation.")
    parser.add_argument(
        "--output",
        help="Path to write structured JSON results (defaults to stdout).",
    )
    parser.add_argument(
        "--csv",
        action="store_true",
        help="Emit per-query metrics as CSV (stdout unless --csv-path provided).",
    )
    parser.add_argument("--csv-path", help="Optional file path to persist CSV output.")
    parser.add_argument("--label", help="Optional run label stored in the JSON output.")
    parser.add_argument(
        "--include-hits",
        action="store_true",
        help="Store retrieved hit summaries for each query in the JSON output.",
    )
    parser.add_argument(
        "--no-query-details",
        action="store_true",
        help="Skip including per-query breakdowns in the JSON output (only aggregates).",
    )
    return parser.parse_args()


def load_queries(path: Path) -> List[Dict[str, Any]]:
    queries: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            queries.append(json.loads(line))
    return queries


def evaluate_query(
    query_payload: Dict[str, Any],
    *,
    k: int,
    endpoint: str,
    timeout: float,
    include_hits: bool,
) -> Dict[str, Any]:
    namespace = query_payload.get("namespace", "pmoves")
    relevant_ids = set(
        query_payload.get("relevant")
        or query_payload.get("gold_ids")
        or []
    )
    body = {
        "query": query_payload["query"],
        "namespace": namespace,
        "k": k,
    }
    response = requests.post(
        f"{endpoint}/hirag/query",
        json=body,
        timeout=timeout,
    )
    response.raise_for_status()
    data = response.json() or {}
    hits = data.get("hits", [])

    rels: List[int] = []
    hit_entries: List[Dict[str, Any]] = []
    for hit in hits:
        chunk_id = hit.get("chunk_id") or (hit.get("payload") or {}).get("chunk_id")
        is_relevant = bool(chunk_id and chunk_id in relevant_ids)
        rels.append(1 if is_relevant else 0)
        hit_entry = {
            "chunk_id": chunk_id,
            "score": hit.get("score"),
            "relevant": is_relevant,
        }
        if include_hits:
            hit_entry["payload"] = hit.get("payload")
        hit_entries.append(hit_entry)

    metrics = {
        "mrr": mrr_at_k(rels, k),
        "ndcg": ndcg_at_k(rels, k),
    }

    return {
        "query": query_payload["query"],
        "namespace": namespace,
        "k": k,
        "metrics": metrics,
        "retrieved": hit_entries,
        "relevant_ids": sorted(relevant_ids),
        "source": query_payload,
    }


def evaluate_dataset(args: argparse.Namespace) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    query_path = Path(args.queries)
    queries = load_queries(query_path)
    results: List[Dict[str, Any]] = []

    for query_payload in queries:
        result = evaluate_query(
            query_payload,
            k=args.k,
            endpoint=args.hirag_url,
            timeout=args.timeout,
            include_hits=args.include_hits,
        )
        results.append(result)

    overall = {
        "count": len(results),
        "mrr": sum(r["metrics"]["mrr"] for r in results) / len(results) if results else 0.0,
        "ndcg": sum(r["metrics"]["ndcg"] for r in results) / len(results) if results else 0.0,
        "k": args.k,
    }

    suite_config = None
    suite_metadata = None
    if args.suites:
        suite_config = load_json(args.suites)
        suite_metadata = artifact_metadata(args.suites)
    suite_results = evaluate_suites(results, suite_config, default_metrics=("mrr", "ndcg"))

    output: Dict[str, Any] = {
        "generated_at": utc_now(),
        "run_label": args.label,
        "endpoint": args.hirag_url,
        "parameters": {"k": args.k, "timeout": args.timeout},
        "dataset": {
            **artifact_metadata(query_path),
            "total_queries": len(queries),
        },
        "overall": overall,
    }

    if not args.no_query_details:
        output["per_query"] = results
    if suite_results:
        output["suites"] = {
            "all": suite_results,
            "by_type": group_suites_by_type(suite_results),
        }
    if suite_metadata:
        output["suite_config"] = suite_metadata

    return output, results


def write_json(output: Dict[str, Any], destination: str | None) -> None:
    serialized = json.dumps(output, indent=2)
    if destination:
        path = Path(destination)
        ensure_directory(path.parent)
        path.write_text(serialized + "\n", encoding="utf-8")
    else:
        print(serialized)


def write_csv(results: List[Dict[str, Any]], destination: str | None) -> None:
    fieldnames = ["query", "namespace", "k", "mrr", "ndcg"]
    rows = [
        {
            "query": r["query"],
            "namespace": r["namespace"],
            "k": r["k"],
            "mrr": r["metrics"]["mrr"],
            "ndcg": r["metrics"]["ndcg"],
        }
        for r in results
    ]
    if destination:
        path = Path(destination)
        ensure_directory(path.parent)
        with path.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
    else:
        writer = csv.DictWriter(os.sys.stdout, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    args = parse_args()
    output, results = evaluate_dataset(args)
    write_json(output, args.output)
    if args.csv:
        write_csv(results, args.csv_path)


if __name__ == "__main__":
    main()
