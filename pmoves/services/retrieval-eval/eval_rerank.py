from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

import requests

try:
    from tabulate import tabulate  # type: ignore
except ImportError:  # pragma: no cover - optional dependency for CLI convenience
    tabulate = None  # noqa: F401

from eval_utils import (
    artifact_metadata,
    ensure_directory,
    evaluate_suites,
    group_suites_by_type,
    load_json,
    utc_now,
)

DEFAULT_GATEWAY = os.environ.get("HIRAG_URL", "http://localhost:8087")
DEFAULT_DATA = os.environ.get("EVAL_DATA", "./datasets/queries.jsonl")
DEFAULT_K = int(os.environ.get("EVAL_K", "10"))


def load_data(path: Path) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            items.append(json.loads(line))
    return items


def recall_at_k(pred_ids: Iterable[str | None], gold_ids: Iterable[str], k: int) -> float:
    gold = [gid for gid in gold_ids if gid]
    if not gold:
        return 0.0
    pred = [pid for pid in pred_ids if pid][:k]
    hits = sum(1 for p in pred if p in gold)
    return hits / len(gold)


def ndcg_at_k(pred_ids: Iterable[str | None], gold_ids: Iterable[str], k: int) -> float:
    gold = [gid for gid in gold_ids if gid]
    idcg = sum(1.0 / math.log2(i + 2) for i in range(min(len(gold), k)))
    if idcg == 0:
        return 0.0
    dcg = 0.0
    for i, pid in enumerate([pid for pid in pred_ids if pid][:k]):
        if pid in gold:
            dcg += 1.0 / math.log2(i + 2)
    return dcg / idcg


def build_request_body(query: Dict[str, Any], *, k: int, use_rerank: bool) -> Dict[str, Any]:
    body = {
        "query": query["query"],
        "namespace": query.get("namespace", "pmoves"),
        "k": k,
        "use_rerank": use_rerank,
    }
    options = query.get("options")
    if isinstance(options, dict):
        body.update(options)
    return body


def query_gateway(endpoint: str, body: Dict[str, Any], timeout: float) -> Dict[str, Any]:
    response = requests.post(f"{endpoint}/hirag/query", json=body, timeout=timeout)
    response.raise_for_status()
    return response.json() or {}


def evaluate_setting(
    queries: List[Dict[str, Any]],
    *,
    use_rerank: bool,
    endpoint: str,
    k: int,
    timeout: float,
    include_hits: bool,
    suite_config: Dict[str, Any] | None,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    per_query: List[Dict[str, Any]] = []
    for query in queries:
        body = build_request_body(query, k=k, use_rerank=use_rerank)
        data = query_gateway(endpoint, body, timeout)
        hits = data.get("hits", [])
        relevant_ids = set(query.get("gold_ids") or query.get("relevant") or [])

        pred_ids: List[str | None] = []
        retrieved = []
        for hit in hits:
            chunk_id = hit.get("chunk_id") or (hit.get("payload") or {}).get("chunk_id")
            pred_ids.append(chunk_id)
            entry = {
                "chunk_id": chunk_id,
                "score": hit.get("score"),
                "relevant": bool(chunk_id and chunk_id in relevant_ids),
            }
            if include_hits:
                entry["payload"] = hit.get("payload")
            retrieved.append(entry)

        metrics = {
            "recall": recall_at_k(pred_ids, relevant_ids, k),
            "ndcg": ndcg_at_k(pred_ids, relevant_ids, k),
        }
        per_query.append(
            {
                "query": query["query"],
                "namespace": query.get("namespace", "pmoves"),
                "k": k,
                "use_rerank": use_rerank,
                "metrics": metrics,
                "retrieved": retrieved,
                "relevant_ids": sorted(relevant_ids),
                "source": query,
            }
        )

    overall_metrics = {
        "recall": sum(item["metrics"]["recall"] for item in per_query) / len(per_query) if per_query else 0.0,
        "ndcg": sum(item["metrics"]["ndcg"] for item in per_query) / len(per_query) if per_query else 0.0,
    }
    suite_results = evaluate_suites(per_query, suite_config, default_metrics=("recall", "ndcg"))
    setting_output: Dict[str, Any] = {
        "label": f"use_rerank={use_rerank}",
        "use_rerank": use_rerank,
        "overall": {
            "count": len(per_query),
            "metrics": overall_metrics,
            "k": k,
        },
    }
    if suite_results:
        setting_output["suites"] = {
            "all": suite_results,
            "by_type": group_suites_by_type(suite_results),
        }
    return setting_output, per_query


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare baseline vs rerank retrieval with optional bias/stress suites.",
    )
    parser.add_argument("--data", default=DEFAULT_DATA, help="Path to evaluation dataset JSONL.")
    parser.add_argument("--k", type=int, default=DEFAULT_K)
    parser.add_argument(
        "--hirag-url",
        default=DEFAULT_GATEWAY,
        help="hi-RAG gateway URL (default from HIRAG_URL).",
    )
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--suites", help="Optional suites JSON file.")
    parser.add_argument("--output", help="Path to write structured JSON results.")
    parser.add_argument("--label", help="Optional run label.")
    parser.add_argument(
        "--include-hits",
        action="store_true",
        help="Include retrieved hit payloads in the JSON output.",
    )
    parser.add_argument(
        "--no-query-details",
        action="store_true",
        help="Omit per-query breakdowns from the JSON output.",
    )
    parser.add_argument("--skip-baseline", action="store_true", help="Skip baseline (no rerank) evaluation.")
    parser.add_argument("--skip-rerank", action="store_true", help="Skip rerank evaluation.")
    parser.add_argument(
        "--table",
        action="store_true",
        help="Print a comparison table to stdout in addition to JSON output.",
    )
    return parser.parse_args()


def build_output(
    *,
    args: argparse.Namespace,
    dataset_path: Path,
    settings_results: List[Dict[str, Any]],
    per_query_details: Dict[str, List[Dict[str, Any]]],
    suite_metadata: Dict[str, Any] | None,
) -> Dict[str, Any]:
    total_queries = len(next(iter(per_query_details.values()))) if per_query_details else 0
    output: Dict[str, Any] = {
        "generated_at": utc_now(),
        "run_label": args.label,
        "endpoint": args.hirag_url,
        "parameters": {"k": args.k, "timeout": args.timeout},
        "dataset": {
            **artifact_metadata(dataset_path),
            "total_queries": total_queries,
        },
        "settings": settings_results,
    }
    if suite_metadata:
        output["suite_config"] = suite_metadata

    if not args.no_query_details:
        output["per_query"] = per_query_details

    if len(settings_results) >= 2:
        baseline = next((s for s in settings_results if not s.get("use_rerank")), None)
        rerank = next((s for s in settings_results if s.get("use_rerank")), None)
        if baseline and rerank:
            comparison = {}
            for metric in ("recall", "ndcg"):
                baseline_value = baseline["overall"]["metrics"].get(metric)
                rerank_value = rerank["overall"]["metrics"].get(metric)
                if baseline_value is None or rerank_value is None:
                    continue
                comparison[metric] = {
                    "baseline": baseline_value,
                    "rerank": rerank_value,
                    "delta": rerank_value - baseline_value,
                }
            if comparison:
                output["comparison"] = comparison
    return output


def write_json(output: Dict[str, Any], destination: str | None) -> None:
    serialized = json.dumps(output, indent=2)
    if destination:
        path = Path(destination)
        ensure_directory(path.parent)
        path.write_text(serialized + "\n", encoding="utf-8")
    else:
        print(serialized)


def maybe_print_table(settings_results: List[Dict[str, Any]]) -> None:
    if not settings_results:
        return
    rows = []
    for setting in settings_results:
        metrics = setting["overall"]["metrics"]
        rows.append(
            [
                setting["label"],
                f"{metrics.get('recall', 0):.4f}",
                f"{metrics.get('ndcg', 0):.4f}",
            ]
        )
    headers = ["setting", "Recall@K", "nDCG@K"]
    if tabulate:
        print(tabulate(rows, headers=headers))
    else:
        # Fallback simple table
        widths = [max(len(str(cell)) for cell in column) for column in zip(headers, *rows)]
        header_line = " | ".join(h.ljust(widths[i]) for i, h in enumerate(headers))
        print(header_line)
        print("-+-".join("-" * w for w in widths))
        for row in rows:
            print(" | ".join(str(cell).ljust(widths[i]) for i, cell in enumerate(row)))


def main() -> None:
    args = parse_args()
    if args.skip_baseline and args.skip_rerank:
        raise SystemExit("Cannot skip both baseline and rerank evaluations.")

    dataset_path = Path(args.data)
    queries = load_data(dataset_path)

    suite_config = None
    suite_metadata = None
    if args.suites:
        suite_config = load_json(args.suites)
        suite_metadata = artifact_metadata(args.suites)

    settings_to_run: List[Tuple[bool, str]] = []
    if not args.skip_baseline:
        settings_to_run.append((False, "baseline"))
    if not args.skip_rerank:
        settings_to_run.append((True, "rerank"))

    settings_results: List[Dict[str, Any]] = []
    per_query_details: Dict[str, List[Dict[str, Any]]] = {}
    for use_rerank, label in settings_to_run:
        setting_output, per_query = evaluate_setting(
            queries,
            use_rerank=use_rerank,
            endpoint=args.hirag_url,
            k=args.k,
            timeout=args.timeout,
            include_hits=args.include_hits,
            suite_config=suite_config,
        )
        setting_output["label"] = label
        if not args.no_query_details:
            setting_output["per_query"] = per_query
        settings_results.append(setting_output)
        per_query_details[label] = per_query

    output = build_output(
        args=args,
        dataset_path=dataset_path,
        settings_results=settings_results,
        per_query_details=per_query_details,
        suite_metadata=suite_metadata,
    )
    write_json(output, args.output)
    if args.table:
        maybe_print_table(settings_results)


if __name__ == "__main__":
    main()
