"""Prometheus metrics exporter for GPU Orchestrator."""

import logging
from typing import Callable, Optional

from prometheus_client import Counter, Gauge, generate_latest, CONTENT_TYPE_LATEST
from fastapi import Response

logger = logging.getLogger(__name__)

# VRAM metrics
gpu_vram_total = Gauge(
    "gpu_vram_total_bytes",
    "Total GPU VRAM in bytes",
    ["gpu_index"],
)
gpu_vram_used = Gauge(
    "gpu_vram_used_bytes",
    "Used GPU VRAM in bytes",
    ["gpu_index"],
)
gpu_vram_free = Gauge(
    "gpu_vram_free_bytes",
    "Free GPU VRAM in bytes",
    ["gpu_index"],
)

# GPU utilization metrics
gpu_utilization = Gauge(
    "gpu_utilization_percent",
    "GPU utilization percentage",
    ["gpu_index"],
)
gpu_temperature = Gauge(
    "gpu_temperature_celsius",
    "GPU temperature in Celsius",
    ["gpu_index"],
)
gpu_power_draw = Gauge(
    "gpu_power_draw_watts",
    "GPU power draw in watts",
    ["gpu_index"],
)

# Model metrics
gpu_model_vram = Gauge(
    "gpu_model_vram_bytes",
    "VRAM usage per model in bytes",
    ["model_id", "provider"],
)
gpu_model_load_count = Counter(
    "gpu_model_loads_total",
    "Total model load operations",
    ["model_id", "provider"],
)
gpu_model_unload_count = Counter(
    "gpu_model_unloads_total",
    "Total model unload operations",
    ["model_id", "provider"],
)
gpu_model_idle_seconds = Gauge(
    "gpu_model_idle_seconds",
    "Seconds since model was last used",
    ["model_id", "provider"],
)

# Queue metrics
gpu_load_queue_depth = Gauge(
    "gpu_model_load_queue_depth",
    "Number of pending load requests",
)
gpu_load_queue_processing = Gauge(
    "gpu_model_load_queue_processing",
    "Number of requests currently being processed",
)

# Session metrics
gpu_active_sessions = Gauge(
    "gpu_active_sessions",
    "Number of active model sessions",
)
gpu_idle_models = Gauge(
    "gpu_idle_models",
    "Number of models idle beyond timeout",
)

# Process metrics
gpu_process_count = Gauge(
    "gpu_process_count",
    "Number of processes using GPU",
    ["gpu_index"],
)


class GpuMetricsExporter:
    """Exports GPU metrics to Prometheus format."""

    def __init__(self, gpu_index: int = 0):
        self.gpu_index = gpu_index
        self._get_status_callback: Optional[Callable] = None

    def set_status_callback(self, callback: Callable) -> None:
        """Set callback to get current GPU status."""
        self._get_status_callback = callback

    async def update_metrics(self) -> None:
        """Update all Prometheus metrics from current state."""
        if not self._get_status_callback:
            logger.warning("Cannot update metrics - no status callback set")
            return

        try:
            status = await self._get_status_callback()
            self._update_gpu_metrics(status)
            self._update_model_metrics(status)
            self._update_process_metrics(status)
        except Exception as e:
            logger.error(f"Error updating metrics: {e}")
            # Mark metrics as stale - set gauge values to -1 to indicate staleness
            gpu_vram_used.labels(gpu_index=str(self.gpu_index)).set(-1)

    def _update_gpu_metrics(self, status: dict) -> None:
        """Update GPU-level metrics."""
        metrics = status.get("metrics", {})
        idx = str(self.gpu_index)

        # VRAM (convert MB to bytes)
        gpu_vram_total.labels(gpu_index=idx).set(
            metrics.get("total_vram_mb", 0) * 1024 * 1024
        )
        gpu_vram_used.labels(gpu_index=idx).set(
            metrics.get("used_vram_mb", 0) * 1024 * 1024
        )
        gpu_vram_free.labels(gpu_index=idx).set(
            metrics.get("free_vram_mb", 0) * 1024 * 1024
        )

        # Utilization
        gpu_utilization.labels(gpu_index=idx).set(
            metrics.get("utilization_percent", 0)
        )
        gpu_temperature.labels(gpu_index=idx).set(
            metrics.get("temperature_c", 0)
        )

        power = metrics.get("power_draw_w")
        if power is not None:
            gpu_power_draw.labels(gpu_index=idx).set(power)

    def _update_model_metrics(self, status: dict) -> None:
        """Update model-level metrics."""
        loaded_models = status.get("loaded_models", {})

        idle_count = 0
        for model_key, model in loaded_models.items():
            model_id = model.get("model_id", "unknown")
            provider = model.get("provider", "unknown")

            # VRAM per model
            gpu_model_vram.labels(model_id=model_id, provider=provider).set(
                model.get("vram_mb", 0) * 1024 * 1024
            )

            # Idle time
            idle_seconds = model.get("idle_seconds", 0)
            gpu_model_idle_seconds.labels(model_id=model_id, provider=provider).set(
                idle_seconds
            )

            if idle_seconds > 300:  # 5 minutes
                idle_count += 1

        gpu_idle_models.set(idle_count)
        gpu_active_sessions.set(len(loaded_models) - idle_count)

    def _update_process_metrics(self, status: dict) -> None:
        """Update process-level metrics."""
        processes = status.get("processes", [])
        gpu_process_count.labels(gpu_index=str(self.gpu_index)).set(len(processes))

    def update_queue_metrics(self, queue_status: dict) -> None:
        """Update queue metrics."""
        gpu_load_queue_depth.set(queue_status.get("pending_count", 0))
        gpu_load_queue_processing.set(queue_status.get("processing_count", 0))

    def record_model_load(self, model_id: str, provider: str) -> None:
        """Record a model load event."""
        gpu_model_load_count.labels(model_id=model_id, provider=provider).inc()

    def record_model_unload(self, model_id: str, provider: str) -> None:
        """Record a model unload event."""
        gpu_model_unload_count.labels(model_id=model_id, provider=provider).inc()


def get_metrics_endpoint():
    """Get FastAPI endpoint for Prometheus metrics."""

    async def metrics_endpoint():
        """Return Prometheus metrics."""
        return Response(
            content=generate_latest(),
            media_type=CONTENT_TYPE_LATEST,
        )

    return metrics_endpoint
