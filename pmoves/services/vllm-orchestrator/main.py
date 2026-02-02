"""vLLM Orchestrator Service - Main Application.

Provides dynamic vLLM deployment with optimal parallelism configuration.
Integrates with node registry for resource discovery and TensorZero
for model registration.
"""

import asyncio
import logging
import os
import signal
import sys
from typing import Any

import structlog
from aiohttp import web

# Import service components (handle hyphenated module name)
import importlib.util

spec = importlib.util.spec_from_file_location(
    "vllm_orchestrator",
    os.path.join(os.path.dirname(__file__), "__init__.py")
)
vllm_orchestrator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vllm_orchestrator)

# Import server module
spec_server = importlib.util.spec_from_file_location(
    "vllm_orchestrator_server",
    os.path.join(os.path.dirname(__file__), "server.py")
)
vllm_server = importlib.util.module_from_spec(spec_server)
spec_server.loader.exec_module(vllm_server)

VLLMOrchestrator = vllm_server.VLLMOrchestrator


# Configure structured logging
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


# Configuration from environment
def get_settings():
    """Get service settings from environment variables."""
    return {
        "nats_url": os.getenv("NATS_URL", "nats://localhost:4222"),
        "api_host": os.getenv("VLLM_ORCHESTRATOR_HOST", "0.0.0.0"),
        "api_port": int(os.getenv("VLLM_ORCHESTRATOR_PORT", "8099")),
        "model_path": os.getenv("VLLM_MODEL_PATH", "/models"),
        "compose_dir": os.getenv("VLLM_COMPOSE_DIR", "/tmp/vllm-compose"),
        "tensorzero_url": os.getenv("TENSORZERO_URL", "http://localhost:3030"),
        "log_level": os.getenv("LOG_LEVEL", "INFO").upper(),
    }


class VLLMOrchestratorService:
    """Main service orchestrator for vLLM deployment.

    Coordinates the orchestrator core with HTTP API and TensorZero integration.
    """

    def __init__(self, settings: dict):
        """Initialize the service.

        Args:
            settings: Service configuration dictionary
        """
        self.settings = settings
        self.orchestrator: VLLMOrchestrator = None
        self._running = False
        self._runner: Any = None
        self._site: Any = None
        self._app: web.Application = None

    async def start(self):
        """Start the vLLM Orchestrator service."""
        if self._running:
            logger.warning("Service already running")
            return

        logger.info("Starting vLLM Orchestrator service")

        # Initialize orchestrator
        self.orchestrator = VLLMOrchestrator(
            nats_url=self.settings["nats_url"],
            model_path=self.settings["model_path"],
            compose_dir=self.settings["compose_dir"],
        )

        # Start orchestrator
        await self.orchestrator.start()
        logger.info("vLLM Orchestrator started", port=self.settings["api_port"])

        # Create and start HTTP API
        self._app = await self._create_app()
        self._runner = web.AppRunner(self._app)
        await self._runner.setup()
        self._site = web.TCPSite(
            self._runner,
            self.settings["api_host"],
            self.settings["api_port"]
        )
        await self._site.start()

        self._running = True
        logger.info("vLLM Orchestrator API started",
                   host=self.settings["api_host"],
                   port=self.settings["api_port"])

    async def stop(self):
        """Stop the vLLM Orchestrator service."""
        if not self._running:
            return

        logger.info("Stopping vLLM Orchestrator service")
        self._running = False

        if self._site:
            await self._site.stop()
        if self._runner:
            await self._runner.cleanup()
        if self.orchestrator:
            await self.orchestrator.stop()

        logger.info("vLLM Orchestrator service stopped")

    async def _create_app(self) -> web.Application:
        """Create the aiohttp application."""
        app = web.Application()

        # Health check endpoint
        async def healthz(request):
            """Health check endpoint."""
            if not self._running:
                return web.json_response(
                    {"status": "unhealthy", "reason": "Service not running"},
                    status=503
                )

            # Check NATS connection
            is_healthy = (
                self.orchestrator and
                self.orchestrator._nc and
                self.orchestrator._nc.is_connected
            )

            if not is_healthy:
                return web.json_response(
                    {"status": "unhealthy", "reason": "NATS not connected"},
                    status=503
                )

            return web.json_response({
                "status": "healthy",
                "instances": len(self.orchestrator._instances) if self.orchestrator else 0,
            })

        # Deploy vLLM endpoint
        async def deploy(request):
            """Deploy a new vLLM instance."""
            try:
                payload = await request.json()

                model_name = payload.get("model_name")
                if not model_name:
                    return web.json_response(
                        {"error": "Missing model_name"},
                        status=400
                    )

                # Create configuration
                config = await self.orchestrator._create_config_for_request(payload)

                if config is None:
                    return web.json_response(
                        {"error": "No suitable nodes available"},
                        status=503
                    )

                # Return configuration
                return web.json_response({
                    "model_name": model_name,
                    "config": config.dict() if hasattr(config, 'dict') else config,
                    "tensorzero_url": self.settings["tensorzero_url"],
                })

            except Exception as e:
                logger.exception("Failed to create vLLM config")
                return web.json_response(
                    {"error": str(e)},
                    status=500
                )

        # List active instances
        async def list_instances(request):
            """List active vLLM instances."""
            if not self.orchestrator:
                return web.json_response({})

            return web.json_response({
                "instances": [
                    {
                        "model_name": name,
                        "config": cfg.dict() if hasattr(cfg, 'dict') else str(cfg),
                    }
                    for name, cfg in self.orchestrator._instances.items()
                ]
            })

        # Stop instance endpoint
        async def stop_instance(request):
            """Stop a vLLM instance."""
            instance_id = request.match_info.get("instance_id")
            if not instance_id or not self.orchestrator:
                return web.json_response({"error": "Invalid instance"}, status=404)

            if instance_id not in self.orchestrator._instances:
                return web.json_response({"error": "Instance not found"}, status=404)

            await self.orchestrator._stop_instance(instance_id)
            return web.json_response({"status": "stopped", "instance_id": instance_id})

        # Model configs endpoint
        async def model_configs(request):
            """Get available model configurations."""
            try:
                from .config import MODEL_CONFIGS
                return web.json_response(MODEL_CONFIGS)
            except ImportError:
                return web.json_response({})

        # Parallelism strategies endpoint
        async def strategies(request):
            """Get available parallelism strategies."""
            from .config import ParallelismStrategy
            return web.json_response({
                "strategies": [s.value for s in ParallelismStrategy]
            })

        # Metrics endpoint
        async def metrics(request):
            """Prometheus metrics endpoint."""
            return web.json_response({
                "service": "vllm-orchestrator",
                "instances": len(self.orchestrator._instances) if self.orchestrator else 0,
                "nats_connected": (
                    self.orchestrator._nc.is_connected
                    if self.orchestrator and self.orchestrator._nc
                    else False
                ),
            })

        app.router.add_get("/healthz", healthz)
        app.router.add_get("/readyz", healthz)
        app.router.add_post("/api/v1/vllm/deploy", deploy)
        app.router.add_get("/api/v1/vllm/instances", list_instances)
        app.router.add_delete("/api/v1/vllm/instances/{instance_id}", stop_instance)
        app.router.add_get("/api/v1/vllm/models", model_configs)
        app.router.add_get("/api/v1/vllm/strategies", strategies)
        app.router.add_get("/metrics", metrics)

        return app


async def main():
    """Main entry point for the vLLM Orchestrator service."""
    # Get settings
    settings = get_settings()

    # Configure log level
    logging.basicConfig(
        level=getattr(logging, settings["log_level"]),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    logger.info("vLLM Orchestrator service starting",
               nats_url=settings["nats_url"],
               api_port=settings["api_port"])

    # Create service
    service = VLLMOrchestratorService(settings)

    # Setup shutdown handlers
    shutdown_event = asyncio.Event()

    def signal_handler(sig, frame):
        logger.info("Received shutdown signal", signal=sig)
        shutdown_event.set()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Start service
    await service.start()

    # Wait for shutdown signal
    await shutdown_event.wait()

    # Stop service
    await service.stop()

    logger.info("vLLM Orchestrator service shutdown complete")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
        sys.exit(0)
    except Exception as e:
        logger.exception("Fatal error in vLLM Orchestrator service")
        sys.exit(1)
