"""Node Registry Service - Main Application.

Provides P2P compute node discovery, capability tracking, and
work allocation queries via NATS and HTTP API.
"""

import asyncio
import logging
import os
import signal
import sys
from contextlib import asynccontextmanager

import structlog
from aiohttp import web

# Import service components
try:
    from .registry import NodeRegistry, SUBJECTS
    from .api import NodeRegistryAPI
    from .storage import SupabaseNodeStore, InMemoryNodeStore
except ImportError:
    # Handle hyphenated module name
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "node_registry",
        os.path.join(os.path.dirname(__file__), "__init__.py")
    )
    node_registry = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(node_registry)
    NodeRegistry = node_registry.NodeRegistry
    SUBJECTS = node_registry.SUBJECTS

    # Import API module
    spec_api = importlib.util.spec_from_file_location(
        "node_registry_api",
        os.path.join(os.path.dirname(__file__), "api.py")
    )
    node_registry_api = importlib.util.module_from_spec(spec_api)
    spec_api.loader.exec_module(node_registry_api)
    NodeRegistryAPI = node_registry_api.NodeRegistryAPI

    # Import storage module
    spec_storage = importlib.util.spec_from_file_location(
        "node_registry_storage",
        os.path.join(os.path.dirname(__file__), "storage.py")
    )
    node_registry_storage = importlib.util.module_from_spec(spec_storage)
    spec_storage.loader.exec_module(node_registry_storage)
    SupabaseNodeStore = node_registry_storage.SupabaseNodeStore
    InMemoryNodeStore = node_registry_storage.InMemoryNodeStore


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
    cache_class=structlog.WriteLogFile,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)


# Configuration from environment
def get_settings():
    """Get service settings from environment variables."""
    return {
        "nats_url": os.getenv("NATS_URL", "nats://localhost:4222"),
        "api_host": os.getenv("NODE_REGISTRY_HOST", "0.0.0.0"),
        "api_port": int(os.getenv("NODE_REGISTRY_PORT", "8082")),
        "stale_threshold_seconds": int(os.getenv("STALE_THRESHOLD_SECONDS", "60")),
        "cleanup_interval_seconds": int(os.getenv("CLEANUP_INTERVAL_SECONDS", "300")),
        "log_level": os.getenv("LOG_LEVEL", "INFO").upper(),
        # Supabase storage (optional)
        "supabase_url": os.getenv("SUPABASE_URL"),
        "supabase_key": os.getenv("SUPABASE_ANON_KEY"),
    }


class NodeRegistryService:
    """Main service orchestrator for Node Registry.

    Coordinates the NATS-based registry and HTTP API.
    """

    def __init__(self, settings: dict):
        """Initialize the service.

        Args:
            settings: Service configuration dictionary
        """
        self.settings = settings
        self.registry: NodeRegistry = None
        self.api: NodeRegistryAPI = None
        self._running = False

    async def start(self):
        """Start the Node Registry service."""
        if self._running:
            logger.warning("Service already running")
            return

        logger.info("Starting Node Registry service")

        # Configure storage backend
        storage = None
        if self.settings.get("supabase_url") and self.settings.get("supabase_key"):
            logger.info("Using Supabase storage backend")
            storage = SupabaseNodeStore(
                url=self.settings["supabase_url"],
                key=self.settings["supabase_key"],
            )
        else:
            logger.info("Using in-memory storage backend")
            storage = InMemoryNodeStore(
                stale_threshold_seconds=self.settings["stale_threshold_seconds"]
            )

        # Initialize registry
        self.registry = NodeRegistry(
            nats_url=self.settings["nats_url"],
            storage=storage,
            stale_threshold_seconds=self.settings["stale_threshold_seconds"],
            cleanup_interval_seconds=self.settings["cleanup_interval_seconds"],
        )

        # Start registry
        await self.registry.start()
        logger.info("Node Registry started", port=self.settings["api_port"])

        # Initialize and start HTTP API
        self.api = NodeRegistryAPI(
            registry=self.registry,
            host=self.settings["api_host"],
            port=self.settings["api_port"],
        )
        await self.api.start()
        logger.info("Node Registry API started",
                   host=self.settings["api_host"],
                   port=self.settings["api_port"])

        self._running = True

    async def stop(self):
        """Stop the Node Registry service."""
        if not self._running:
            return

        logger.info("Stopping Node Registry service")
        self._running = False

        if self.api:
            await self.api.stop()

        if self.registry:
            await self.registry.stop()

        logger.info("Node Registry service stopped")

    async def health_check(self):
        """Perform health check for the service."""
        if not self._running:
            return {"status": "unhealthy", "reason": "Service not running"}

        # Check registry health
        if self.registry and self.registry._nc:
            is_connected = self.registry._nc.is_connected
            if not is_connected:
                return {"status": "unhealthy", "reason": "NATS not connected"}

        return {"status": "healthy"}


async def create_app(service: NodeRegistryService) -> web.Application:
    """Create the aiohttp application for the service.

    Args:
        service: NodeRegistryService instance

    Returns:
        aiohttp Application
    """
    app = web.Application()

    # Health check endpoint
    async def healthz(request):
        """Health check endpoint."""
        health = await service.health_check()
        status = 200 if health["status"] == "healthy" else 503
        return web.json_response(health, status=status)

    # Readiness endpoint
    async def ready(request):
        """Readiness check endpoint."""
        return web.json_response({"status": "ready" if service._running else "not ready"})

    # Metrics endpoint for Prometheus
    async def metrics(request):
        """Prometheus metrics endpoint."""
        if service.registry and service.registry.storage:
            stats = service.registry.storage.get_stats()
            return web.json_response(stats)
        return web.json_response({})

    app.router.add_get("/healthz", healthz)
    app.router.add_get("/readyz", ready)
    app.router.add_get("/metrics", metrics)

    return app


async def main():
    """Main entry point for the Node Registry service."""
    # Get settings
    settings = get_settings()

    # Configure log level
    logging.basicConfig(
        level=getattr(logging, settings["log_level"]),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    logger.info("Node Registry service starting",
               nats_url=settings["nats_url"],
               api_port=settings["api_port"])

    # Create service
    service = NodeRegistryService(settings)

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

    logger.info("Node Registry service shutdown complete")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
        sys.exit(0)
    except Exception as e:
        logger.exception("Fatal error in Node Registry service")
        sys.exit(1)
