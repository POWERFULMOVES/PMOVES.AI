"""Node Registry Service - Main Application.

Provides P2P compute node discovery, capability tracking, and
work allocation queries via NATS and HTTP API.
"""

import asyncio
import logging
import os
import signal
import sys

import structlog
from aiohttp import web

# Import service components.
#
# WHY (D3): this entry point used to load its own submodules with
# importlib.util.spec_from_file_location(...). A module loaded that way has
# no parent package, so `from ..resource_detector.models import ...` inside
# registry.py / storage.py / api.py raised "attempted relative import with no
# known parent package" -- the service could not start at all. The package
# directory is now `node_registry`, so the relative imports resolve
# natively; the fallback below covers a plain script launch
# (`python pmoves/services/node_registry/main.py`), where the module still
# has no package context.
try:
    from .registry import NodeRegistry, SUBJECTS
    from .api import NodeRegistryAPI
    from .storage import SupabaseNodeStore, InMemoryNodeStore
except ImportError:
    # Script mode: no package context. Make the repo root importable and
    # load the REAL package by its canonical name instead of by file path.
    import pathlib

    _REPO_ROOT = str(pathlib.Path(__file__).resolve().parents[3])
    if _REPO_ROOT not in sys.path:
        sys.path.insert(0, _REPO_ROOT)

    from pmoves.services.node_registry.registry import NodeRegistry, SUBJECTS
    from pmoves.services.node_registry.api import NodeRegistryAPI
    from pmoves.services.node_registry.storage import (
        SupabaseNodeStore,
        InMemoryNodeStore,
    )


# Configure structured logging
#
# WHY NO `cache_class=`: it was here as `cache_class=structlog.WriteLogFile`,
# and NEITHER half of that has ever existed in a released structlog.
# `structlog.WriteLogFile` is not exported by structlog 21.5.0, 22.3.0,
# 24.4.0 or 26.1.0 (the wheels were unpacked and grepped to confirm);
# `structlog.WriteLogger` is what those versions export. And `cache_class` is
# not in `configure()`'s signature in any of them either -- the supported
# parameters are processors, wrapper_class, context_class, logger_factory and
# cache_logger_on_first_use. So the call raised AttributeError (the missing
# attribute) and would have raised TypeError (the unexpected keyword) even if
# the attribute had existed. Caching is done by `cache_logger_on_first_use`,
# which is the mechanism structlog actually supports.
#
# The module therefore could not be IMPORTED, in any environment, ever --
# which is why nothing noticed: no test, no script and no service imported
# this entry point until the mesh compatibility ratchet did, and it failed
# there. `structlog` is pinned at 24.4.0 in pmoves/requirements.txt and
# unpinned in pmoves/requirements-tests.txt, so the merge gate (which installs
# the unpinned set and resolved 26.1.0) failed where a pinned 24.4.0
# environment would have failed differently.
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
        "nats_url": os.getenv("NATS_URL", "nats://nats:4222"),
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
    except Exception:
        logger.exception("Fatal error in Node Registry service")
        sys.exit(1)
