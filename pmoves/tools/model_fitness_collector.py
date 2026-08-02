#!/usr/bin/env python3
"""Model Fitness Collector — ETL bridge from TensorZero inference telemetry to model fitness records.

G3 of the model lifecycle pipeline. Scrapes TensorZero gateway's ``/metrics``
Prometheus endpoint for per-model inference aggregates (no ClickHouse needed —
works with observability disabled), normalizes them via
``normalize_model_fitness()``, and POSTs them to the model-registry
``/api/model-fitness`` endpoint where they are persisted + CHIT-signed + NATS-broadcast.

Telemetry sources:
  - TensorZero ``GET /metrics`` — Prometheus exposition format with
    ``tensorzero_requests_total{function_name=...}`` and latency histograms.
    Always available regardless of ``[gateway.observability].enabled``.
  - Agent Zero + Archon route all LLM calls through TensorZero, so their
    inference telemetry is captured at the gateway layer automatically.
  - Tracing overlay (``docker-compose.tracing.yml``) extends this with
    Jaeger spans when enabled.

Usage:
    # Auto-collect from TensorZero /metrics:
    python -m pmoves.tools.model_fitness_collector --auto

    # Manual mode (supply metrics for a single model):
    python -m pmoves.tools.model_fitness_collector \
        --model-id qwen35_4b \
        --source tensorzero \
        --lane edge \
        --success-rate 0.95 \
        --latency-ms 3200 \
        --tokens-per-second 45

    # Dry-run (compute score, don't POST):
    python -m pmoves.tools.model_fitness_collector \
        --model-id qwen35_4b --source tensorzero --lane edge \
        --success-rate 0.95 --dry-run
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from pmoves.services.common.model_fitness import build_model_fitness_event


TENSORZERO_URL = os.environ.get(
    "TENSORZERO_URL", "http://localhost:3030"
)
MODEL_REGISTRY_URL = os.environ.get(
    "MODEL_REGISTRY_URL", "http://localhost:8110"
)
CHIT_PASSPHRASE = os.environ.get("CHIT_PASSPHRASE", "")


def scrape_prometheus() -> dict[str, dict[str, Any]]:
    """Scrape TensorZero /metrics (Prometheus exposition format).

    Returns a dict keyed by model/function name with aggregated metrics.
    No ClickHouse dependency — works with observability disabled.
    """
    import urllib.request
    import urllib.error
    import re

    url = f"{TENSORZERO_URL}/metrics"
    try:
        req = urllib.request.Request(url)
        resp = urllib.request.urlopen(req, timeout=10)
        raw = resp.read().decode("utf-8")
    except Exception:
        return {}

    results: dict[str, dict[str, Any]] = {}

    for line in raw.splitlines():
        line = line.strip()
        if line.startswith("#") or not line:
            continue

        # Parse: metric_name{labels} value
        m = re.match(r'([a-z_:]+)\{([^}]*)\}\s+([0-9.eE+-]+)', line)
        if not m:
            continue

        metric_name, labels_str, value_str = m.groups()
        labels: dict[str, str] = {}
        for pair in labels_str.split(","):
            if "=" in pair:
                k, v = pair.split("=", 1)
                labels[k.strip()] = v.strip('"')

        fn = labels.get("function_name", labels.get("model_name", ""))
        if not fn:
            continue

        if fn not in results:
            results[fn] = {"total_requests": 0, "latency_sum": 0.0, "latency_count": 0}

        try:
            value = float(value_str)
        except ValueError:
            continue

        if metric_name.endswith("_total") and "requests" in metric_name:
            results[fn]["total_requests"] = int(value)
        elif "latency" in metric_name.lower():
            if labels.get("le") == "+Inf":
                results[fn]["latency_sum"] = value
            results[fn]["latency_count"] += 1

    for fn, data in results.items():
        if data["latency_count"] > 0:
            data["avg_latency_ms"] = (data["latency_sum"] / max(data["latency_count"], 1)) * 1000

    return results


def tensorzero_available() -> bool:
    """Check if TensorZero gateway /health responds."""
    import urllib.request
    import urllib.error

    try:
        req = urllib.request.Request(f"{TENSORZERO_URL}/health")
        resp = urllib.request.urlopen(req, timeout=5)
        return resp.status == 200
    except Exception:
        return False


def compute_metrics(
    row: dict[str, Any],
) -> dict[str, Any]:
    """Convert a ClickHouse aggregate row to TensorZero metrics dict."""
    total = int(row.get("total_requests", 0))
    successful = int(row.get("successful", 0))
    fallback = int(row.get("fallback_count", 0))
    avg_latency = float(row.get("avg_latency_ms", 0) or 0)
    avg_tps = float(row.get("avg_tps", 0) or 0)

    return {
        "success_rate": successful / total if total else 0.5,
        "task_score": successful / total if total else 0.5,
        "tool_success_rate": 0.5,
        "structured_output_valid_rate": 0.5,
        "latency_ms": avg_latency,
        "tokens_per_second": avg_tps,
        "cost_per_1k_tokens": None,
        "fallback_rate": fallback / total if total else 0.0,
    }


def post_fitness(event: dict[str, Any], dry_run: bool = False) -> dict[str, Any]:
    """POST a fitness event to the model-registry endpoint."""
    if dry_run:
        return {"ok": True, "dry_run": True, "score": event.get("score")}

    import urllib.request

    model_id = event["model_id"]
    url = f"{MODEL_REGISTRY_URL}/api/model-fitness"
    body = json.dumps({
        "model_id": model_id,
        "source": event["source"],
        "lane": event["lane"],
        "tensorzero_metrics": event["metrics"]["tensorzero"],
        "training_metrics": event["metrics"].get("training", {}),
        "run_id": event.get("run_id"),
        "score": event["score"],
    }).encode()

    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    resp = urllib.request.urlopen(req, timeout=10)
    return json.loads(resp.read())


def run_auto(dry_run: bool = False) -> None:
    """Auto-collect from TensorZero /metrics and POST fitness records."""
    if not tensorzero_available():
        print("[fitness-collector] TensorZero gateway not reachable")
        print("[fitness-collector] Start it with: make -C pmoves up")
        return

    results = scrape_prometheus()
    if not results:
        print("[fitness-collector] No inference data in TensorZero /metrics yet")
        print("[fitness-collector] Metrics populate as LLM calls flow through the gateway")
        return

    print(f"[fitness-collector] Found {len(results)} models with inference data")
    for fn, data in results.items():
        if data.get("total_requests", 0) == 0:
            continue
        metrics = compute_metrics(data)
        event = build_model_fitness_event(
            model_id=fn,
            source="tensorzero",
            lane="inference",
            tensorzero_metrics=metrics,
            agent_id="fitness-collector",
            passphrase=CHIT_PASSPHRASE or None,
        )
        result = post_fitness(event, dry_run=dry_run)
        print(
            f"  {fn}: score={event['score']:.4f} "
            f"requests={data.get('total_requests', 0)} "
            f"{'[dry-run]' if dry_run else '[posted]'}"
        )


def run_manual(
    model_id: str,
    source: str,
    lane: str,
    success_rate: float | None = None,
    latency_ms: float | None = None,
    tokens_per_second: float | None = None,
    cost_per_1k: float | None = None,
    fallback_rate: float | None = None,
    training_score: float | None = None,
    training_loss: float | None = None,
    publish_eligible: bool = False,
    dry_run: bool = False,
) -> None:
    """Manual mode — supply metrics for a single model."""
    tensorzero_metrics: dict[str, Any] = {}
    if success_rate is not None:
        tensorzero_metrics["success_rate"] = success_rate
    if latency_ms is not None:
        tensorzero_metrics["latency_ms"] = latency_ms
    if tokens_per_second is not None:
        tensorzero_metrics["tokens_per_second"] = tokens_per_second
    if cost_per_1k is not None:
        tensorzero_metrics["cost_per_1k_tokens"] = cost_per_1k
    if fallback_rate is not None:
        tensorzero_metrics["fallback_rate"] = fallback_rate

    training_metrics: dict[str, Any] = {}
    if training_score is not None:
        training_metrics["eval_score"] = training_score
    if training_loss is not None:
        training_metrics["loss"] = training_loss
    training_metrics["publish_eligible"] = publish_eligible

    event = build_model_fitness_event(
        model_id=model_id,
        source=source,
        lane=lane,
        tensorzero_metrics=tensorzero_metrics,
        training_metrics=training_metrics,
        agent_id="fitness-collector",
        passphrase=CHIT_PASSPHRASE or None,
    )

    print(f"[fitness-collector] {model_id}: score={event['score']:.4f}")
    print(f"  normalized: {json.dumps(event['metrics']['normalized'], indent=2)}")

    result = post_fitness(event, dry_run=dry_run)
    if dry_run:
        print(f"  [dry-run] would POST to {MODEL_REGISTRY_URL}/api/model-fitness")
    else:
        print(f"  [posted] {result}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Model Fitness Collector — TensorZero telemetry to fitness records"
    )
    parser.add_argument(
        "--auto",
        action="store_true",
        help="Auto-collect from ClickHouse observability store",
    )
    parser.add_argument(
        "--model-id",
        help="Manual mode: model ID (e.g. qwen35_4b)",
    )
    parser.add_argument("--source", default="tensorzero")
    parser.add_argument("--lane", default="inference")
    parser.add_argument("--success-rate", type=float)
    parser.add_argument("--latency-ms", type=float)
    parser.add_argument("--tokens-per-second", type=float)
    parser.add_argument("--cost-per-1k", type=float)
    parser.add_argument("--fallback-rate", type=float)
    parser.add_argument("--training-score", type=float)
    parser.add_argument("--training-loss", type=float)
    parser.add_argument("--publish-eligible", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.auto:
        run_auto(dry_run=args.dry_run)
    elif args.model_id:
        run_manual(
            model_id=args.model_id,
            source=args.source,
            lane=args.lane,
            success_rate=args.success_rate,
            latency_ms=args.latency_ms,
            tokens_per_second=args.tokens_per_second,
            cost_per_1k=args.cost_per_1k,
            fallback_rate=args.fallback_rate,
            training_score=args.training_score,
            training_loss=args.training_loss,
            publish_eligible=args.publish_eligible,
            dry_run=args.dry_run,
        )
    else:
        parser.print_help()
        print("\nEither --auto or --model-id is required")


if __name__ == "__main__":
    main()
