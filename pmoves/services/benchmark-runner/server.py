"""Benchmark Runner server with NATS integration.

Provides a service for running LLM benchmarks and publishing
results to TensorZero and NATS for distributed coordination.
"""

import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, Optional

from nats.aio.client import Client as NATS
from nats.aio.msg import Msg

from .benchmark import BenchmarkConfig, BenchmarkRunner, BenchmarkResult
from .comparison import BenchmarkComparator, ComparisonReport

logger = logging.getLogger(__name__)

# NATS subjects for benchmark coordination
SUBJECTS = {
    "request": "compute.benchmark.request.v1",
    "result": "compute.benchmark.result.v1",
    "status": "compute.benchmark.status.v1",
    "cancel": "compute.benchmark.cancel.v1",
}


class BenchmarkServer:
    """NATS-enabled benchmark runner service.

    Subscribes to benchmark requests and executes them asynchronously.
    Publishes results and status updates.
    """

    def __init__(
        self,
        nats_url: str = "nats://localhost:4222",
        output_dir: str = "/tmp/benchmark-results",
        tensorzero_url: str = "http://localhost:3030",
    ):
        """Initialize benchmark server.

        Args:
            nats_url: NATS server URL
            output_dir: Directory for benchmark outputs
            tensorzero_url: TensorZero gateway URL
        """
        self.nats_url = nats_url
        self.output_dir = output_dir
        self.tensorzero_url = tensorzero_url

        self._nc: Optional[NATS] = None
        self._runner = BenchmarkRunner(output_dir, tensorzero_url)
        self._comparator = BenchmarkComparator(results_dir=output_dir)
        self._running = False

        # Track active benchmarks
        self._active_benchmarks: Dict[str, asyncio.Task] = {}
        self._benchmark_results: Dict[str, BenchmarkResult] = {}

    async def start(self):
        """Start the benchmark server."""
        if self._running:
            return

        self._nc = NATS()
        await self._nc.connect(self.nats_url)

        # Subscribe to benchmark requests
        await self._nc.subscribe(
            SUBJECTS["request"],
            "benchmark-workers",
            self._handle_benchmark_request,
        )

        # Subscribe to status queries
        await self._nc.subscribe(
            SUBJECTS["status"],
            "benchmark-workers",
            self._handle_status_request,
        )

        # Subscribe to cancel requests
        await self._nc.subscribe(
            SUBJECTS["cancel"],
            "benchmark-workers",
            self._handle_cancel_request,
        )

        self._running = True
        logger.info(f"Benchmark server started on {self.nats_url}")
        logger.info(f"Listening on: {SUBJECTS['request']}")

    async def stop(self):
        """Stop the benchmark server."""
        if not self._running:
            return

        self._running = False

        # Cancel active benchmarks
        for benchmark_id, task in list(self._active_benchmarks.items()):
            task.cancel()
            logger.info(f"Cancelled benchmark {benchmark_id[:8]}...")

        # Wait for tasks to complete
        if self._active_benchmarks:
            await asyncio.gather(*self._active_benchmarks.values(), return_exceptions=True)

        if self._nc:
            await self._nc.close()
            self._nc = None

        logger.info("Benchmark server stopped")

    async def _handle_benchmark_request(self, msg: Msg):
        """Handle incoming benchmark request."""
        try:
            data = json.loads(msg.data)

            # Validate request
            required = ["model_name", "model_path"]
            if not all(k in data for k in required):
                await self._publish_error(
                    msg.reply,
                    f"Missing required fields: {required}",
                )
                return

            # Create benchmark configuration
            config = BenchmarkConfig(
                model_name=data["model_name"],
                model_path=data["model_path"],
                tensor_parallel_size=data.get("tensor_parallel_size", 1),
                pipeline_parallel_size=data.get("pipeline_parallel_size", 1),
                gpu_indices=data.get("gpu_indices"),
                batch_sizes=data.get("batch_sizes", [1, 8, 16, 32]),
                context_lengths=data.get("context_lengths", [128, 512, 2048, 4096]),
                num_iterations=data.get("num_iterations", 3),
                output_dir=self.output_dir,
                publish_to_tensorzero=data.get("publish_to_tensorzero", True),
                tensorzero_url=self.tensorzero_url,
            )

            # Start benchmark
            benchmark_id = await self._run_benchmark(config)

            # Send initial response with benchmark ID
            response = {
                "status": "started",
                "benchmark_id": benchmark_id,
                "model_name": config.model_name,
                "started_at": datetime.now().isoformat(),
            }

            if msg.reply:
                await self._nc.publish(msg.reply, json.dumps(response).encode())

        except Exception as e:
            logger.error(f"Error handling benchmark request: {e}")
            if msg.reply:
                await self._publish_error(msg.reply, str(e))

    async def _run_benchmark(self, config: BenchmarkConfig) -> str:
        """Run a benchmark in the background."""
        import uuid

        benchmark_id = str(uuid.uuid4())

        # Create task for background execution
        task = asyncio.create_task(
            self._benchmark_wrapper(benchmark_id, config)
        )
        self._active_benchmarks[benchmark_id] = task

        # Setup callback to remove from active when done
        task.add_done_callback(
            lambda t: self._active_benchmarks.pop(benchmark_id, None)
        )

        return benchmark_id

    async def _benchmark_wrapper(
        self,
        benchmark_id: str,
        config: BenchmarkConfig,
    ):
        """Wrapper for benchmark execution with result publishing."""
        try:
            # Run benchmark
            result = await self._runner.run_benchmark(config)

            # Store result
            self._benchmark_results[benchmark_id] = result

            # Publish result
            await self._publish_result(benchmark_id, result)

        except Exception as e:
            logger.error(f"Benchmark {benchmark_id[:8]}... failed: {e}")
            await self._publish_error(
                SUBJECTS["result"],
                f"Benchmark failed: {e}",
                benchmark_id=benchmark_id,
            )

    async def _publish_result(self, benchmark_id: str, result: BenchmarkResult):
        """Publish benchmark result to NATS."""
        if not self._nc:
            return

        message = {
            "benchmark_id": benchmark_id,
            "status": "completed" if result.validation_passed else "failed",
            "timestamp": datetime.now().isoformat(),
            "result": result.to_dict(),
        }

        await self._nc.publish(
            SUBJECTS["result"],
            json.dumps(message).encode(),
        )

        logger.info(
            f"Published benchmark result: {benchmark_id[:8]}... "
            f"({result.tokens_per_second:.1f} tokens/sec)"
        )

    async def _handle_status_request(self, msg: Msg):
        """Handle status query request."""
        try:
            data = json.loads(msg.data)
            benchmark_id = data.get("benchmark_id")

            if benchmark_id:
                # Get specific benchmark status
                status = await self._runner.get_benchmark_status(benchmark_id)
                result = self._benchmark_results.get(benchmark_id)

                response = {
                    "benchmark_id": benchmark_id,
                    "status": status,
                    "result": result.to_dict() if result else None,
                }
            else:
                # Get all active benchmarks
                response = {
                    "active_benchmarks": list(self._active_benchmarks.keys()),
                    "completed_count": len(self._benchmark_results),
                }

            if msg.reply:
                await self._nc.publish(msg.reply, json.dumps(response).encode())

        except Exception as e:
            logger.error(f"Error handling status request: {e}")

    async def _handle_cancel_request(self, msg: Msg):
        """Handle benchmark cancellation request."""
        try:
            data = json.loads(msg.data)
            benchmark_id = data.get("benchmark_id")

            if not benchmark_id:
                await self._publish_error(
                    msg.reply,
                    "Missing benchmark_id",
                )
                return

            cancelled = await self._runner.cancel_benchmark(benchmark_id)

            response = {
                "benchmark_id": benchmark_id,
                "cancelled": cancelled,
            }

            if msg.reply:
                await self._nc.publish(msg.reply, json.dumps(response).encode())

        except Exception as e:
            logger.error(f"Error handling cancel request: {e}")

    async def _publish_error(
        self,
        subject: str,
        error: str,
        benchmark_id: Optional[str] = None,
    ):
        """Publish error message."""
        if not self._nc:
            return

        message = {
            "error": error,
            "timestamp": datetime.now().isoformat(),
        }
        if benchmark_id:
            message["benchmark_id"] = benchmark_id

        await self._nc.publish(
            subject,
            json.dumps(message).encode(),
        )

    async def run_comparison(
        self,
        baseline_id: str,
        current_id: str,
    ) -> Optional[ComparisonReport]:
        """Run a comparison between two benchmarks.

        Args:
            baseline_id: Baseline benchmark ID
            current_id: Current benchmark ID

        Returns:
            ComparisonReport if successful
        """
        return await asyncio.to_thread(
            self._comparator.compare,
            baseline_id,
            current_id,
        )

    def get_stats(self) -> Dict[str, Any]:
        """Get server statistics.

        Returns:
            Dict with server stats
        """
        return {
            "status": "running" if self._running else "stopped",
            "nats_url": self.nats_url,
            "active_benchmarks": len(self._active_benchmarks),
            "completed_benchmarks": len(self._benchmark_results),
            "active_ids": list(self._active_benchmarks.keys()),
        }


async def run_server(
    nats_url: str = "nats://localhost:4222",
    output_dir: str = "/tmp/benchmark-results",
    tensorzero_url: str = "http://localhost:3030",
):
    """Run benchmark server as standalone service.

    Args:
        nats_url: NATS server URL
        output_dir: Output directory for benchmarks
        tensorzero_url: TensorZero gateway URL
    """
    server = BenchmarkServer(
        nats_url=nats_url,
        output_dir=output_dir,
        tensorzero_url=tensorzero_url,
    )

    await server.start()

    try:
        # Keep running
        while True:
            await asyncio.sleep(60)

            # Log stats periodically
            stats = server.get_stats()
            logger.info(
                f"Benchmark server: {stats['active_benchmarks']} active, "
                f"{stats['completed_benchmarks']} completed"
            )

    except asyncio.CancelledError:
        pass
    finally:
        await server.stop()


if __name__ == "__main__":
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    nats_url = os.getenv("NATS_URL", "nats://localhost:4222")
    output_dir = os.getenv("BENCHMARK_OUTPUT_DIR", "/tmp/benchmark-results")
    tensorzero_url = os.getenv("TENSORZERO_URL", "http://localhost:3030")

    try:
        asyncio.run(run_server(nats_url, output_dir, tensorzero_url))
    except KeyboardInterrupt:
        logger.info("Benchmark server stopped by user")
