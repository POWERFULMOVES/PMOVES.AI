"""GPU Orchestrator Service - Main Application.

Provides dynamic GPU resource management, model lifecycle control,
and VRAM visibility for PMOVES.AI deployments.
"""

import asyncio
import logging
import sys
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import get_settings
from api import router as api_router
from api.routes import set_dependencies
from models import ModelRegistry
from services import (
    ModelLifecycleManager,
    OllamaClient,
    TtsClient,
    VllmClient,
    VramTracker,
)
from nats import GpuNatsPublisher
from metrics import GpuMetricsExporter, get_metrics_endpoint

# Configure logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)

# Global instances
vram_tracker: VramTracker
model_registry: ModelRegistry
lifecycle_manager: ModelLifecycleManager
nats_publisher: GpuNatsPublisher
metrics_exporter: GpuMetricsExporter


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global vram_tracker, model_registry, lifecycle_manager, nats_publisher, metrics_exporter

    settings = get_settings()
    logger.info("Starting GPU Orchestrator", port=settings.port)

    try:
        # Initialize VRAM tracker
        vram_tracker = VramTracker(gpu_index=settings.gpu_index)
        metrics = vram_tracker.get_metrics()
        log_fn = logger.warning if metrics.is_mock else logger.info
        log_fn(
            "GPU detected",
            name=metrics.name,
            total_vram_mb=metrics.total_vram_mb,
            is_mock=metrics.is_mock,
            gpu_index=settings.gpu_index,
        )

        # Initialize model registry
        model_registry = ModelRegistry(settings.model_registry_path)
        logger.info(
            "Model registry loaded",
            model_count=len(model_registry.models),
        )

        # Initialize provider clients
        ollama_client = OllamaClient(settings.ollama_url)
        vllm_client = VllmClient(settings.vllm_url)
        tts_client = TtsClient(settings.tts_url)

        # Initialize lifecycle manager
        lifecycle_manager = ModelLifecycleManager(
            vram_tracker=vram_tracker,
            model_registry=model_registry,
            ollama_client=ollama_client,
            vllm_client=vllm_client,
            tts_client=tts_client,
        )
        await lifecycle_manager.start()

        # Initialize metrics exporter (before callbacks that reference it)
        metrics_exporter = GpuMetricsExporter(gpu_index=settings.gpu_index)

        # Initialize NATS publisher
        nats_publisher = GpuNatsPublisher(
            nats_url=settings.nats_url,
            status_interval=settings.status_publish_interval,
        )
        connected = await nats_publisher.connect()
        if not connected:
            logger.warning("NATS connection failed, running without message publishing")

        # Set up callbacks
        async def get_status_for_nats():
            status = await lifecycle_manager.get_status()
            return status.to_dict()

        nats_publisher.set_status_callback(get_status_for_nats)
        metrics_exporter.set_status_callback(get_status_for_nats)
        await nats_publisher.start_status_loop()

        # Set up lifecycle callbacks for NATS events
        async def on_model_loaded(model_key: str):
            model = lifecycle_manager.loaded_models.get(model_key)
            if model:
                await nats_publisher.publish_model_loaded(model_key, model.vram_mb)
                metrics_exporter.record_model_load(model.model_id, model.provider)

        async def on_model_unloaded(model_key: str):
            await nats_publisher.publish_model_unloaded(model_key)
            parts = model_key.split("/", 1)
            if len(parts) == 2:
                metrics_exporter.record_model_unload(parts[1], parts[0])

        lifecycle_manager.set_on_load_callback(on_model_loaded)
        lifecycle_manager.set_on_unload_callback(on_model_unloaded)

        # Set dependencies for routes
        set_dependencies(lifecycle_manager, vram_tracker, model_registry)

        logger.info("GPU Orchestrator started successfully")

    except Exception as e:
        logger.error("Failed to start GPU Orchestrator", error=str(e))
        raise

    yield

    # Shutdown
    logger.info("Shutting down GPU Orchestrator")
    try:
        if nats_publisher:
            await nats_publisher.disconnect()
        if lifecycle_manager:
            await lifecycle_manager.stop()
        if vram_tracker:
            vram_tracker.shutdown()
    except Exception as e:
        logger.error("Error during shutdown", error=str(e))
    logger.info("GPU Orchestrator shutdown complete")


# Create FastAPI app
app = FastAPI(
    title="GPU Orchestrator",
    description="Dynamic GPU resource management for PMOVES.AI",
    version="1.0.0",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routes
app.include_router(api_router)


# Health check endpoint
@app.get("/healthz")
async def health_check():
    """Health check endpoint."""
    from fastapi import status

    try:
        metrics = vram_tracker.get_metrics()
        if metrics.is_mock:
            return {
                "status": "degraded",
                "error": "GPU monitoring unavailable - running in mock mode",
            }, status.HTTP_503_SERVICE_UNAVAILABLE
        return {
            "status": "healthy",
            "gpu": metrics.name,
            "vram_usage_percent": round(metrics.vram_usage_percent, 2),
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
        }, status.HTTP_503_SERVICE_UNAVAILABLE


# Prometheus metrics endpoint
@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    try:
        # Update metrics before returning
        if metrics_exporter:
            await metrics_exporter.update_metrics()
            queue_status = lifecycle_manager.get_queue_status()
            metrics_exporter.update_queue_metrics(queue_status)

        endpoint = get_metrics_endpoint()
        return await endpoint()
    except Exception as e:
        logger.error("Error generating metrics", error=str(e))
        # Return empty metrics on error to prevent scraping failures
        from fastapi import Response
        from prometheus_client import CONTENT_TYPE_LATEST
        return Response(content=b"", media_type=CONTENT_TYPE_LATEST, status_code=503)


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper()),
        format="%(message)s",
        stream=sys.stdout,
    )

    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
    )
