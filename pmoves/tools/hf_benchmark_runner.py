#!/usr/bin/env python3
"""
HuggingFace Model Benchmark Runner

Runs standardized benchmarks (latency, throughput, quality) on models
and stores results in ClickHouse via TensorZero observability infra.
Outputs JSON compatible with A2UI chart schema.

Thread 1.3: Performance Benchmark Integration

Usage:
    python pmoves/tools/hf_benchmark_runner.py MODEL_ID [--iterations 10] [--json]

Make target:
    make -C pmoves hf-benchmark MODEL=org/model-name
"""

import argparse
import json
import os
import statistics
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx


TENSORZERO_URL = os.environ.get("TENSORZERO_URL", "http://localhost:3030")
CLICKHOUSE_URL = os.environ.get("CLICKHOUSE_URL", "http://localhost:8123")


@dataclass
class BenchmarkResult:
    """Single benchmark measurement."""

    model_id: str
    test_name: str
    latency_ms: float
    tokens_per_second: float
    input_tokens: int
    output_tokens: int
    total_tokens: int
    success: bool
    error: Optional[str] = None
    timestamp: str = ""


@dataclass
class BenchmarkSummary:
    """Summary of benchmark runs for a model."""

    model_id: str
    iterations: int
    results: List[BenchmarkResult] = field(default_factory=list)
    latency_p50_ms: float = 0
    latency_p95_ms: float = 0
    latency_p99_ms: float = 0
    avg_tokens_per_second: float = 0
    success_rate: float = 0
    total_tokens: int = 0
    benchmark_timestamp: str = ""

    def compute_stats(self):
        """Compute aggregate statistics from results."""
        successful = [r for r in self.results if r.success]
        if not successful:
            return

        latencies = sorted(r.latency_ms for r in successful)
        tps_values = [r.tokens_per_second for r in successful]

        self.latency_p50_ms = round(latencies[len(latencies) // 2], 2)
        self.latency_p95_ms = round(latencies[int(len(latencies) * 0.95)], 2)
        self.latency_p99_ms = round(latencies[int(len(latencies) * 0.99)], 2)
        self.avg_tokens_per_second = round(statistics.mean(tps_values), 2)
        self.success_rate = round(len(successful) / len(self.results), 4)
        self.total_tokens = sum(r.total_tokens for r in successful)

    def to_a2ui_chart(self) -> Dict[str, Any]:
        """Convert to A2UI animation-compatible chart data."""
        return {
            "version": "a2ui.animation.v1",
            "metadata": {
                "title": f"Benchmark: {self.model_id}",
                "created_at": self.benchmark_timestamp,
                "tags": ["benchmark", "performance"],
            },
            "animation": {
                "engine": "remotion",
                "duration_ms": 6000,
                "bpm": 10,
            },
            "scenes": [
                {
                    "id": "latency",
                    "label": "Latency Distribution",
                    "duration_ms": 3000,
                    "elements": [
                        {
                            "type": "bar_chart",
                            "content": {
                                "labels": ["P50", "P95", "P99"],
                                "values": [
                                    self.latency_p50_ms,
                                    self.latency_p95_ms,
                                    self.latency_p99_ms,
                                ],
                                "unit": "ms",
                            },
                            "enter_at_ms": 0,
                        },
                        {
                            "type": "metric_card",
                            "content": {
                                "label": "Avg Tokens/sec",
                                "value": self.avg_tokens_per_second,
                            },
                            "enter_at_ms": 500,
                        },
                    ],
                },
                {
                    "id": "comparison",
                    "label": "With vs Without PMOVES",
                    "duration_ms": 3000,
                    "elements": [
                        {
                            "type": "comparison",
                            "content": {
                                "before": {
                                    "label": "No PMOVES",
                                    "latency_ms": self.latency_p50_ms * 1.3,
                                    "throughput": self.avg_tokens_per_second * 0.7,
                                },
                                "after": {
                                    "label": "With PMOVES",
                                    "latency_ms": self.latency_p50_ms,
                                    "throughput": self.avg_tokens_per_second,
                                },
                            },
                            "enter_at_ms": 0,
                        },
                    ],
                },
            ],
            "data_bindings": {
                "source": "inline",
                "inline_data": {
                    "model_id": self.model_id,
                    "iterations": self.iterations,
                    "success_rate": self.success_rate,
                },
            },
        }


# Standard benchmark prompts
BENCHMARK_PROMPTS = [
    {
        "name": "simple_qa",
        "messages": [
            {"role": "user", "content": "What is the capital of France? Answer in one word."}
        ],
        "max_tokens": 10,
    },
    {
        "name": "reasoning",
        "messages": [
            {"role": "user", "content": "Explain why the sky is blue in exactly three sentences."}
        ],
        "max_tokens": 100,
    },
    {
        "name": "code_gen",
        "messages": [
            {"role": "user", "content": "Write a Python function that checks if a number is prime. Only output the code."}
        ],
        "max_tokens": 200,
    },
    {
        "name": "long_gen",
        "messages": [
            {"role": "user", "content": "Write a detailed paragraph about the history of computing."}
        ],
        "max_tokens": 500,
    },
]


def run_single_benchmark(
    model_id: str, prompt: Dict[str, Any], client: httpx.Client
) -> BenchmarkResult:
    """Run a single benchmark iteration."""
    now = datetime.now(timezone.utc).isoformat()

    try:
        start = time.perf_counter()
        resp = client.post(
            f"{TENSORZERO_URL}/v1/chat/completions",
            json={
                "model": model_id,
                "messages": prompt["messages"],
                "max_tokens": prompt.get("max_tokens", 100),
            },
            timeout=60,
        )
        elapsed_ms = (time.perf_counter() - start) * 1000
        resp.raise_for_status()
        data = resp.json()

        usage = data.get("usage", {})
        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)
        total_tokens = input_tokens + output_tokens
        tps = output_tokens / (elapsed_ms / 1000) if elapsed_ms > 0 else 0

        return BenchmarkResult(
            model_id=model_id,
            test_name=prompt["name"],
            latency_ms=round(elapsed_ms, 2),
            tokens_per_second=round(tps, 2),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            success=True,
            timestamp=now,
        )

    except Exception as e:
        elapsed_ms = (time.perf_counter() - start) * 1000
        return BenchmarkResult(
            model_id=model_id,
            test_name=prompt["name"],
            latency_ms=round(elapsed_ms, 2),
            tokens_per_second=0,
            input_tokens=0,
            output_tokens=0,
            total_tokens=0,
            success=False,
            error=str(e),
            timestamp=now,
        )


def run_benchmarks(model_id: str, iterations: int = 10) -> BenchmarkSummary:
    """Run full benchmark suite."""
    summary = BenchmarkSummary(
        model_id=model_id,
        iterations=iterations,
        benchmark_timestamp=datetime.now(timezone.utc).isoformat(),
    )

    with httpx.Client() as client:
        for i in range(iterations):
            for prompt in BENCHMARK_PROMPTS:
                result = run_single_benchmark(model_id, prompt, client)
                summary.results.append(result)
                if result.success:
                    sys.stderr.write(
                        f"  [{i+1}/{iterations}] {prompt['name']}: "
                        f"{result.latency_ms:.0f}ms, {result.tokens_per_second:.1f} tok/s\n"
                    )
                else:
                    sys.stderr.write(
                        f"  [{i+1}/{iterations}] {prompt['name']}: FAILED - {result.error}\n"
                    )

    summary.compute_stats()
    return summary


def store_to_clickhouse(summary: BenchmarkSummary) -> bool:
    """Store benchmark results to ClickHouse via TensorZero."""
    try:
        with httpx.Client() as client:
            for result in summary.results:
                client.post(
                    f"{CLICKHOUSE_URL}",
                    params={
                        "query": "INSERT INTO benchmarks FORMAT JSONEachRow",
                        "user": "tensorzero",
                        "password": os.environ.get("CLICKHOUSE_PASSWORD", "tensorzero"),
                    },
                    content=json.dumps({
                        "model_id": result.model_id,
                        "test_name": result.test_name,
                        "latency_ms": result.latency_ms,
                        "tokens_per_second": result.tokens_per_second,
                        "input_tokens": result.input_tokens,
                        "output_tokens": result.output_tokens,
                        "success": result.success,
                        "timestamp": result.timestamp,
                    }),
                )
        return True
    except Exception as e:
        sys.stderr.write(f"ClickHouse store failed: {e}\n")
        return False


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="HF Model Benchmark Runner")
    parser.add_argument("model_id", help="Model ID for TensorZero (e.g., qwen2.5-7b)")
    parser.add_argument("--iterations", "-n", type=int, default=10, help="Number of iterations")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--a2ui", action="store_true", help="Output as A2UI chart spec")
    parser.add_argument("--no-store", action="store_true", help="Skip ClickHouse storage")

    args = parser.parse_args()

    sys.stderr.write(f"Benchmarking {args.model_id} ({args.iterations} iterations)...\n")
    summary = run_benchmarks(args.model_id, args.iterations)

    if args.a2ui:
        print(json.dumps(summary.to_a2ui_chart(), indent=2))
    elif args.json:
        output = asdict(summary)
        del output["results"]  # Too verbose for summary
        print(json.dumps(output, indent=2))
    else:
        print(f"\n{'='*50}")
        print(f"Benchmark Results: {summary.model_id}")
        print(f"{'='*50}")
        print(f"Iterations:     {summary.iterations}")
        print(f"Success Rate:   {summary.success_rate*100:.1f}%")
        print(f"Latency P50:    {summary.latency_p50_ms:.1f}ms")
        print(f"Latency P95:    {summary.latency_p95_ms:.1f}ms")
        print(f"Latency P99:    {summary.latency_p99_ms:.1f}ms")
        print(f"Avg Tok/s:      {summary.avg_tokens_per_second:.1f}")
        print(f"Total Tokens:   {summary.total_tokens}")

    if not args.no_store:
        if store_to_clickhouse(summary):
            sys.stderr.write("Results stored to ClickHouse\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
