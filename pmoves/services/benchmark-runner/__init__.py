"""Benchmark Runner Service - Automated LLM performance testing.

Provides integration with llama-throughput-lab for benchmarking
LLM inference performance and tracking results over time.

Usage:
    from pmoves.services.benchmark_runner import (
        BenchmarkRunner,
        BenchmarkConfig,
        BenchmarkServer,
        run_server,
    )

    # Run a quick benchmark
    runner = BenchmarkRunner()
    config = BenchmarkConfig(
        model_name="llama-3-8b",
        model_path="meta-llama/Meta-Llama-3-8B",
        tensor_parallel_size=1,
    )
    result = await runner.run_benchmark(config)
    print(f"Throughput: {result.tokens_per_second} tokens/sec")

    # Run as service
    await run_server(nats_url="nats://localhost:4222")

NATS Subjects:
    - compute.benchmark.request.v1: Submit benchmark requests
    - compute.benchmark.result.v1: Receive benchmark results
    - compute.benchmark.status.v1: Query benchmark status
    - compute.benchmark.cancel.v1: Cancel running benchmarks
"""

from .benchmark import (
    BenchmarkConfig,
    BenchmarkResult,
    BenchmarkRunner,
    run_quick_benchmark,
)

from .comparison import (
    BenchmarkComparator,
    ComparisonReport,
    calculate_geometric_mean,
    calculate_score,
)

from .server import BenchmarkServer, SUBJECTS, run_server

__all__ = [
    # Benchmark
    "BenchmarkConfig",
    "BenchmarkResult",
    "BenchmarkRunner",
    "run_quick_benchmark",
    # Comparison
    "BenchmarkComparator",
    "ComparisonReport",
    "calculate_geometric_mean",
    "calculate_score",
    # Server
    "BenchmarkServer",
    "SUBJECTS",
    "run_server",
]
