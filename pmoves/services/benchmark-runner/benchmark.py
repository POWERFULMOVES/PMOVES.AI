"""Benchmark execution using llama-throughput-lab.

Integrates llama-throughput-lab for automated LLM performance testing.
Publishes results to TensorZero for metrics tracking and analysis.
"""

import asyncio
import dataclasses
import json
import logging
import os
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class BenchmarkConfig:
    """Configuration for a benchmark run."""

    model_name: str  # e.g., "meta-llama/Llama-3-8B"
    model_path: str  # Local path or HuggingFace hub path
    tensor_parallel_size: int = 1
    pipeline_parallel_size: int = 1
    gpu_indices: Optional[List[int]] = None  # Specific GPUs to use

    # Benchmark parameters
    batch_sizes: List[int] = dataclasses.field(default_factory=lambda: [1, 8, 16, 32])
    context_lengths: List[int] = dataclasses.field(default_factory=lambda: [128, 512, 2048, 4096])
    num_iterations: int = 3

    # Output options
    output_dir: str = "/tmp/benchmark-results"
    publish_to_tensorzero: bool = True
    tensorzero_url: str = "http://localhost:3030"


@dataclasses.dataclass
class BenchmarkResult:
    """Results from a benchmark run."""

    benchmark_id: str
    model_name: str
    timestamp: datetime

    # Hardware info
    gpu_name: str
    gpu_count: int
    tensor_parallel_size: int
    pipeline_parallel_size: int

    # Performance metrics
    tokens_per_second: float
    time_to_first_token_ms: float
    time_per_output_token_ms: float

    # Memory metrics
    vram_used_mb: int
    vram_peak_mb: int
    system_ram_mb: int

    # Test parameters
    batch_size: int
    context_length: int
    quantization: str

    # Validation
    validation_passed: bool
    validation_error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "benchmark_id": self.benchmark_id,
            "model_name": self.model_name,
            "timestamp": self.timestamp.isoformat(),
            "hardware": {
                "gpu_name": self.gpu_name,
                "gpu_count": self.gpu_count,
                "tensor_parallel_size": self.tensor_parallel_size,
                "pipeline_parallel_size": self.pipeline_parallel_size,
            },
            "performance": {
                "tokens_per_second": round(self.tokens_per_second, 2),
                "time_to_first_token_ms": round(self.time_to_first_token_ms, 2),
                "time_per_output_token_ms": round(self.time_per_output_token_ms, 2),
            },
            "memory": {
                "vram_used_mb": self.vram_used_mb,
                "vram_peak_mb": self.vram_peak_mb,
                "system_ram_mb": self.system_ram_mb,
            },
            "test_params": {
                "batch_size": self.batch_size,
                "context_length": self.context_length,
                "quantization": self.quantization,
            },
            "validation": {
                "passed": self.validation_passed,
                "error": self.validation_error,
            },
        }


class BenchmarkRunner:
    """Execute and manage LLM benchmarks using llama-throughput-lab."""

    def __init__(
        self,
        output_dir: str = "/tmp/benchmark-results",
        tensorzero_url: str = "http://localhost:3030",
    ):
        """Initialize benchmark runner.

        Args:
            output_dir: Directory for benchmark output files
            tensorzero_url: URL for TensorZero gateway
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.tensorzero_url = tensorzero_url
        self._running_benchmarks: Dict[str, asyncio.Task] = {}

    async def check_dependencies(self) -> Dict[str, bool]:
        """Check if required tools are available.

        Returns:
            Dict mapping tool name to availability status
        """
        dependencies = {
            "llama-throughput-lab": False,
            "nvidia-smi": False,
            "python": False,
        }

        # Check for llama-throughput-lab
        try:
            result = await asyncio.to_thread(
                subprocess.run,
                ["llama-throughput-lab", "--help"],
                capture_output=True,
                timeout=5,
            )
            dependencies["llama-throughput-lab"] = result.returncode == 0
        except FileNotFoundError:
            logger.warning("llama-throughput-lab not found in PATH")
            dependencies["llama-throughput-lab"] = False
        except subprocess.TimeoutExpired:
            logger.error("llama-throughput-lab timed out - process may be hung")
            dependencies["llama-throughput-lab"] = False

        # Check for nvidia-smi
        try:
            result = await asyncio.to_thread(
                subprocess.run,
                ["nvidia-smi", "--version"],
                capture_output=True,
                timeout=5,
            )
            dependencies["nvidia-smi"] = result.returncode == 0
        except FileNotFoundError:
            logger.warning("nvidia-smi not found in PATH")
            dependencies["nvidia-smi"] = False
        except subprocess.TimeoutExpired:
            logger.error("nvidia-smi timed out - GPU may be locked")
            dependencies["nvidia-smi"] = False

        # Check for Python
        try:
            result = await asyncio.to_thread(
                subprocess.run,
                ["python3", "--version"],
                capture_output=True,
                timeout=5,
            )
            dependencies["python"] = result.returncode == 0
        except FileNotFoundError:
            logger.warning("python3 not found in PATH")
            dependencies["python"] = False
        except subprocess.TimeoutExpired:
            logger.error("python3 timed out")
            dependencies["python"] = False

        return dependencies

    async def get_gpu_info(self) -> Dict[str, Any]:
        """Get GPU information for benchmark context.

        Returns:
            Dict with GPU details
        """
        try:
            result = await asyncio.to_thread(
                subprocess.run,
                [
                    "nvidia-smi",
                    "--query-gpu=name,memory.total,driver_version,cuda_version",
                    "--format=csv,noheader",
                ],
                capture_output=True,
                text=True,
                timeout=5,
            )

            if result.returncode != 0:
                return {"gpu_name": "unknown", "gpu_count": 0}

            gpus = []
            for line in result.stdout.strip().splitlines():
                parts = [p.strip() for p in line.split(",")]
                if len(parts) >= 4:
                    gpus.append({
                        "name": parts[0],
                        "memory_mb": int(parts[1].split()[0]),
                        "driver": parts[2],
                        "cuda": parts[3],
                    })

            return {
                "gpu_count": len(gpus),
                "gpus": gpus,
                "primary_gpu": gpus[0]["name"] if gpus else "unknown",
            }

        except Exception as e:
            logger.warning(f"Could not get GPU info: {e}")
            return {"gpu_name": "unknown", "gpu_count": 0}

    async def run_benchmark(
        self,
        config: BenchmarkConfig,
        background: bool = False,
    ) -> Optional[str]:
        """Run a benchmark with the given configuration.

        Args:
            config: Benchmark configuration
            background: If True, run in background and return benchmark ID

        Returns:
            Benchmark ID if synchronous, None if background
        """
        import uuid

        benchmark_id = str(uuid.uuid4())

        if background:
            task = asyncio.create_task(
                self._run_benchmark_impl(benchmark_id, config)
            )
            self._running_benchmarks[benchmark_id] = task
            return benchmark_id

        await self._run_benchmark_impl(benchmark_id, config)
        return benchmark_id

    async def _run_benchmark_impl(
        self,
        benchmark_id: str,
        config: BenchmarkConfig,
    ) -> BenchmarkResult:
        """Implementation of benchmark execution."""

        # Build llama-throughput-lab command
        cmd = self._build_benchmark_cmd(config, benchmark_id)

        logger.info(f"Running benchmark: {config.model_name}")
        logger.debug(f"Command: {' '.join(cmd)}")

        # Set GPU visibility if specified
        env = os.environ.copy()
        if config.gpu_indices:
            env["CUDA_VISIBLE_DEVICES"] = ",".join(map(str, config.gpu_indices))

        # Run benchmark
        try:
            result = await asyncio.to_thread(
                subprocess.run,
                cmd,
                capture_output=True,
                text=True,
                timeout=3600,  # 1 hour timeout
                env=env,
            )

            if result.returncode != 0:
                logger.error(f"Benchmark failed: {result.stderr}")
                return self._create_error_result(benchmark_id, config, result.stderr)

            # Parse output
            benchmark_result = await self._parse_benchmark_output(
                benchmark_id, config, result.stdout
            )

            # Publish to TensorZero if configured
            if config.publish_to_tensorzero:
                await self._publish_to_tensorzero(benchmark_result)

            return benchmark_result

        except subprocess.TimeoutExpired:
            logger.error("Benchmark timed out after 1 hour")
            return self._create_error_result(benchmark_id, config, "Benchmark timed out")
        except Exception as e:
            logger.error(f"Benchmark error: {e}")
            return self._create_error_result(benchmark_id, config, str(e))

    def _build_benchmark_cmd(
        self,
        config: BenchmarkConfig,
        benchmark_id: str,
    ) -> List[str]:
        """Build llama-throughput-lab command line."""
        output_file = self.output_dir / f"{benchmark_id}.json"

        cmd = [
            "llama-throughput-lab",
            "--model", config.model_path,
            "--output", str(output_file),
            "--tensor-parallel-size", str(config.tensor_parallel_size),
        ]

        if config.pipeline_parallel_size > 1:
            cmd.extend(["--pipeline-parallel-size", str(config.pipeline_parallel_size)])

        # Add test parameters
        for batch_size in config.batch_sizes:
            cmd.extend(["--batch-size", str(batch_size)])

        for context_len in config.context_lengths:
            cmd.extend(["--context-length", str(context_len)])

        cmd.extend(["--num-iterations", str(config.num_iterations)])

        return cmd

    async def _parse_benchmark_output(
        self,
        benchmark_id: str,
        config: BenchmarkConfig,
        output: str,
    ) -> BenchmarkResult:
        """Parse benchmark output into structured result."""

        # Try to parse JSON output file first
        json_file = self.output_dir / f"{benchmark_id}.json"
        if json_file.exists():
            try:
                content = await asyncio.to_thread(json_file.read_text)
                data = json.loads(content)
                return self._parse_json_result(benchmark_id, config, data)
            except Exception as e:
                logger.warning(f"Could not parse JSON output: {e}")

        # Fallback to parsing stdout
        return self._parse_text_output(benchmark_id, config, output)

    def _parse_json_result(
        self,
        benchmark_id: str,
        config: BenchmarkConfig,
        data: Dict,
    ) -> BenchmarkResult:
        """Parse JSON output from llama-throughput-lab."""

        # Get GPU info
        gpu_info = data.get("gpu", {})
        gpu_name = gpu_info.get("name", "unknown")
        gpu_count = gpu_info.get("count", 1)

        # Get performance metrics
        perf = data.get("performance", {})
        tps = perf.get("tokens_per_second", 0.0)
        ttft = perf.get("time_to_first_token_ms", 0.0)
        tpot = perf.get("time_per_output_token_ms", 0.0)

        # Get memory metrics
        mem = data.get("memory", {})
        vram_used = mem.get("vram_used_mb", 0)
        vram_peak = mem.get("vram_peak_mb", 0)
        system_ram = mem.get("system_ram_mb", 0)

        # Get test parameters
        test_params = data.get("test_parameters", {})
        batch_size = test_params.get("batch_size", config.batch_sizes[0] if config.batch_sizes else 1)
        context_length = test_params.get("context_length", config.context_lengths[0] if config.context_lengths else 4096)

        return BenchmarkResult(
            benchmark_id=benchmark_id,
            model_name=config.model_name,
            timestamp=datetime.now(),
            gpu_name=gpu_name,
            gpu_count=gpu_count,
            tensor_parallel_size=config.tensor_parallel_size,
            pipeline_parallel_size=config.pipeline_parallel_size,
            tokens_per_second=tps,
            time_to_first_token_ms=ttft,
            time_per_output_token_ms=tpot,
            vram_used_mb=vram_used,
            vram_peak_mb=vram_peak,
            system_ram_mb=system_ram,
            batch_size=batch_size,
            context_length=context_length,
            quantization=data.get("quantization", "fp16"),
            validation_passed=data.get("validation", {}).get("passed", True),
            validation_error=data.get("validation", {}).get("error"),
        )

    def _parse_text_output(
        self,
        benchmark_id: str,
        config: BenchmarkConfig,
        output: str,
    ) -> BenchmarkResult:
        """Parse text output from llama-throughput-lab."""

        # Parse tokens/sec
        tps_match = re.search(r"Throughput:\s*([\d.]+)\s*tokens/s", output)
        tps = float(tps_match.group(1)) if tps_match else 0.0

        # Parse TTFT
        ttft_match = re.search(r"TTFT:\s*([\d.]+)\s*ms", output)
        ttft = float(ttft_match.group(1)) if ttft_match else 0.0

        # Parse memory usage
        mem_match = re.search(r"VRAM:\s*(\d+)\s*MB", output)
        vram_used = int(mem_match.group(1)) if mem_match else 0

        return BenchmarkResult(
            benchmark_id=benchmark_id,
            model_name=config.model_name,
            timestamp=datetime.now(),
            gpu_name="unknown",  # Would need separate detection
            gpu_count=config.tensor_parallel_size * config.pipeline_parallel_size,
            tensor_parallel_size=config.tensor_parallel_size,
            pipeline_parallel_size=config.pipeline_parallel_size,
            tokens_per_second=tps,
            time_to_first_token_ms=ttft,
            time_per_output_token_ms=0.0,  # Not typically in text output
            vram_used_mb=vram_used,
            vram_peak_mb=vram_used,
            system_ram_mb=0,
            batch_size=config.batch_sizes[0] if config.batch_sizes else 1,
            context_length=config.context_lengths[0] if config.context_lengths else 4096,
            quantization="fp16",
            validation_passed=True,
        )

    def _create_error_result(
        self,
        benchmark_id: str,
        config: BenchmarkConfig,
        error_message: str,
    ) -> BenchmarkResult:
        """Create a result object for failed benchmarks."""
        return BenchmarkResult(
            benchmark_id=benchmark_id,
            model_name=config.model_name,
            timestamp=datetime.now(),
            gpu_name="unknown",
            gpu_count=0,
            tensor_parallel_size=config.tensor_parallel_size,
            pipeline_parallel_size=config.pipeline_parallel_size,
            tokens_per_second=0.0,
            time_to_first_token_ms=0.0,
            time_per_output_token_ms=0.0,
            vram_used_mb=0,
            vram_peak_mb=0,
            system_ram_mb=0,
            batch_size=0,
            context_length=0,
            quantization="unknown",
            validation_passed=False,
            validation_error=error_message,
        )

    async def _publish_to_tensorzero(self, result: BenchmarkResult) -> bool:
        """Publish benchmark results to TensorZero.

        Args:
            result: Benchmark result to publish

        Returns:
            True if published successfully
        """
        import httpx

        # Construct metrics endpoint URL
        url = f"{self.tensorzero_url}/metrics/benchmark"

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    url,
                    json=result.to_dict(),
                    headers={"Content-Type": "application/json"},
                )

                if response.status_code == 200:
                    logger.info(f"Published benchmark {result.benchmark_id[:8]}... to TensorZero")
                    return True
                else:
                    logger.warning(
                        f"Failed to publish to TensorZero: {response.status_code} - {response.text}"
                    )
                    return False

        except Exception as e:
            logger.error(f"Error publishing to TensorZero: {e}")
            return False

    async def get_benchmark_status(self, benchmark_id: str) -> Optional[str]:
        """Get status of a running benchmark.

        Args:
            benchmark_id: Benchmark ID to check

        Returns:
            Status string ("running", "completed", "failed") or None if not found
        """
        if benchmark_id not in self._running_benchmarks:
            return None

        task = self._running_benchmarks[benchmark_id]

        if task.done():
            del self._running_benchmarks[benchmark_id]
            try:
                result = await task
                return "completed" if result.validation_passed else "failed"
            except Exception:
                return "failed"

        return "running"

    async def cancel_benchmark(self, benchmark_id: str) -> bool:
        """Cancel a running benchmark.

        Args:
            benchmark_id: Benchmark ID to cancel

        Returns:
            True if benchmark was cancelled
        """
        if benchmark_id not in self._running_benchmarks:
            return False

        task = self._running_benchmarks[benchmark_id]
        task.cancel()
        del self._running_benchmarks[benchmark_id]

        logger.info(f"Cancelled benchmark {benchmark_id[:8]}...")
        return True

    def list_benchmarks(self) -> List[str]:
        """List all benchmark IDs (running and recent).

        Returns:
            List of benchmark IDs
        """
        return list(self._running_benchmarks.keys())


async def run_quick_benchmark(
    model_path: str,
    model_name: str,
    gpu_count: int = 1,
    output_dir: str = "/tmp/benchmark-results",
) -> BenchmarkResult:
    """Run a quick benchmark with default parameters.

    Args:
        model_path: Path to model or HuggingFace identifier
        model_name: Name of the model
        gpu_count: Number of GPUs to use
        output_dir: Output directory for results

    Returns:
        BenchmarkResult with performance metrics
    """
    runner = BenchmarkRunner(output_dir=output_dir)

    config = BenchmarkConfig(
        model_name=model_name,
        model_path=model_path,
        tensor_parallel_size=gpu_count,
        batch_sizes=[1, 8],
        context_lengths=[512, 2048],
        num_iterations=2,
    )

    return await runner.run_benchmark(config)
