"""Work Marshaling Service - Main Application.

P2P work allocation and distribution service. Receives work requests
from the network and allocates them to appropriate nodes based on
capabilities, availability, and location.
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
    "work_marshaling",
    os.path.join(os.path.dirname(__file__), "__init__.py")
)
work_marshaling = importlib.util.module_from_spec(spec)
spec.loader.exec_module(work_marshaling)

WorkMarshaling = work_marshaling.WorkMarshaling
SUBJECTS = work_marshaling.SUBJECTS


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
        "registry_url": os.getenv("NODE_REGISTRY_URL", "http://localhost:8082"),
        "api_host": os.getenv("WORK_MARSHALING_HOST", "0.0.0.0"),
        "api_port": int(os.getenv("WORK_MARSHALING_PORT", "8100")),
        "assignment_timeout_seconds": int(os.getenv("ASSIGNMENT_TIMEOUT_SECONDS", "30")),
        "max_retries": int(os.getenv("MAX_RETRIES", "3")),
        "stale_check_interval_seconds": int(os.getenv("STALE_CHECK_INTERVAL_SECONDS", "60")),
        "log_level": os.getenv("LOG_LEVEL", "INFO").upper(),
    }


class WorkMarshalingService:
    """Main service orchestrator for work marshaling.

    Coordinates the marshaling core with HTTP API and NATS integration.
    """

    def __init__(self, settings: dict):
        """Initialize the service.

        Args:
            settings: Service configuration dictionary
        """
        self.settings = settings
        self.marshaling: WorkMarshaling = None
        self._running = False
        self._runner: Any = None
        self._site: Any = None
        self._app: web.Application = None

    async def start(self):
        """Start the Work Marshaling service."""
        if self._running:
            logger.warning("Service already running")
            return

        logger.info("Starting Work Marshaling service")

        # Initialize marshaling
        self.marshaling = WorkMarshaling(
            nats_url=self.settings["nats_url"],
            registry_url=self.settings["registry_url"],
            assignment_timeout_seconds=self.settings["assignment_timeout_seconds"],
            max_retries=self.settings["max_retries"],
            stale_check_interval_seconds=self.settings["stale_check_interval_seconds"],
        )

        # Start marshaling
        await self.marshaling.start()
        logger.info("Work Marshaling started", port=self.settings["api_port"])

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
        logger.info("Work Marshaling API started",
                   host=self.settings["api_host"],
                   port=self.settings["api_port"])

    async def stop(self):
        """Stop the Work Marshaling service."""
        if not self._running:
            return

        logger.info("Stopping Work Marshaling service")
        self._running = False

        if self._site:
            await self._site.stop()
        if self._runner:
            await self._runner.cleanup()
        if self.marshaling:
            await self.marshaling.stop()

        logger.info("Work Marshaling service stopped")

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
                self.marshaling and
                self.marshaling._nc and
                self.marshaling._nc.is_connected
            )

            if not is_healthy:
                return web.json_response(
                    {"status": "unhealthy", "reason": "NATS not connected"},
                    status=503
                )

            return web.json_response({
                "status": "healthy",
                "pending": len(self.marshaling._pending) if self.marshaling else 0,
            })

        # Submit work endpoint
        async def submit_work(request):
            """Submit a new work item."""
            try:
                payload = await request.json()
                result = await self.marshaling.submit_work(payload)
                return web.json_response(result)
            except Exception as e:
                logger.exception("Failed to submit work")
                return web.json_response({"error": str(e)}, status=500)

        # List work items endpoint
        async def list_work(request):
            """List active work items."""
            if not self.marshaling:
                return web.json_response([])

            status_filter = request.query.get("status")
            items = []

            for work_id, item in self.marshaling._work_items.items():
                if status_filter and item.status != status_filter:
                    continue
                items.append({
                    "work_id": work_id,
                    "status": item.status,
                    "assigned_node": item.assigned_node,
                    "created_at": item.created_at.isoformat(),
                })

            return web.json_response({"items": items})

        # Get work item status
        async def get_work_status(request):
            """Get status of a specific work item."""
            work_id = request.match_info.get("work_id")
            if not work_id or not self.marshaling or work_id not in self.marshaling._work_items:
                return web.json_response({"error": "Work item not found"}, status=404)

            item = self.marshaling._work_items[work_id]
            return web.json_response({
                "work_id": work_id,
                "status": item.status,
                "assigned_node": item.assigned_node,
                "retry_count": item.retry_count,
                "error_message": item.error_message,
                "created_at": item.created_at.isoformat(),
                "updated_at": item.updated_at.isoformat(),
            })

        # Statistics endpoint
        async def stats(request):
            """Get marshaling statistics."""
            if not self.marshaling:
                return web.json_response({})

            return web.json_response(self.marshaling._stats.to_dict())

        # NATS subjects endpoint
        async def subjects(request):
            """Get configured NATS subjects."""
            return web.json_response(SUBJECTS)

        # Metrics endpoint for Prometheus
        async def metrics(request):
            """Prometheus metrics endpoint."""
            if self.marshaling and self.marshaling._stats:
                return web.json_response(self.marshaling._stats.to_dict())
            return web.json_response({})

        app.router.add_get("/healthz", healthz)
        app.router.add_get("/readyz", healthz)
        app.router.add_post("/api/v1/work/submit", submit_work)
        app.router.add_get("/api/v1/work", list_work)
        app.router.add_get("/api/v1/work/{work_id}", get_work_status)
        app.router.add_get("/api/v1/stats", stats)
        app.router.add_get("/api/v1/subjects", subjects)
        app.router.add_get("/metrics", metrics)

        return app


async def main():
    """Main entry point for the Work Marshaling service."""
    # Get settings
    settings = get_settings()

    # Configure log level
    logging.basicConfig(
        level=getattr(logging, settings["log_level"]),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    logger.info("Work Marshaling service starting",
               nats_url=settings["nats_url"],
               api_port=settings["api_port"])

    # Create service
    service = WorkMarshalingService(settings)

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

    logger.info("Work Marshaling service shutdown complete")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
        sys.exit(0)
    except Exception as e:
        logger.exception("Fatal error in Work Marshaling service")
        sys.exit(1)
