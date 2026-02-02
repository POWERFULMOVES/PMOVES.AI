"""Resource Detector Service - Main Application.

Detects system hardware (CPU, GPU, RAM) and generates appropriate
docker-compose resource limits for PMOVES.AI services.

Usage:
    python -m pmoves.services.resource_detector.main
    or
    python services/resource-detector/main.py
"""

import asyncio
import json
import logging
import os
import signal
import sys
from contextlib import asynccontextmanager
from typing import Any, Dict

import structlog
from aiohttp import web

# Import service components (handle hyphenated module name)
import importlib.util

spec = importlib.util.spec_from_file_location(
    "resource_detector",
    os.path.join(os.path.dirname(__file__), "__init__.py")
)
resource_detector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(resource_detector)

get_hardware_profile = resource_detector.get_hardware_profile
generate_resource_limits = resource_detector.generate_resource_limits


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
        "host": os.getenv("RESOURCE_DETECTOR_HOST", "0.0.0.0"),
        "port": int(os.getenv("RESOURCE_DETECTOR_PORT", "8083")),
        "log_level": os.getenv("LOG_LEVEL", "INFO").upper(),
        "cache_ttl_seconds": int(os.getenv("CACHE_TTL_SECONDS", "60")),
    }


class ResourceDetectorService:
    """Main service for hardware detection and resource allocation.

    Provides HTTP API for:
    - GET /profile - Get hardware profile
    - GET /limits - Get docker-compose resource limits
    - GET /healthz - Health check
    """

    def __init__(self, settings: dict):
        """Initialize the service.

        Args:
            settings: Service configuration dictionary
        """
        self.settings = settings
        self._running = False
        self._profile = None
        self._limits = None
        self._last_profile_update = None
        self._runner: Any = None
        self._site: Any = None
        self._app: web.Application = None

    async def _refresh_profile(self):
        """Refresh hardware profile and limits."""
        try:
            self._profile = get_hardware_profile()
            self._limits = generate_resource_limits()
            self._last_profile_update = asyncio.get_event_loop().time()

            logger.info("Hardware profile refreshed",
                       cpu_cores=self._profile.cpu.total_threads,
                       ram_gb=self._profile.memory.total_gb,
                       gpu_count=len(self._profile.gpus),
                       tier=self._profile.tier.value)
        except Exception as e:
            logger.exception("Failed to refresh hardware profile")
            # Use default profile on error
            self._profile = self._get_default_profile()
            self._limits = {}

    def _get_default_profile(self):
        """Get default profile for graceful degradation."""
        from resource_detector import (
            HardwareProfile,
            CpuInfo,
            SystemMemory,
            NetworkInfo,
            NodeTier,
        )
        return HardwareProfile(
            cpu=CpuInfo(
                cores=4,
                threads_per_core=1,
                total_threads=4,
                model_name="Unknown",
                mhz_per_cpu=2000,
            ),
            memory=SystemMemory(
                total_mb=16384,
                total_gb=16.0,
                available_mb=16384,
                available_gb=16.0,
            ),
            gpus=[],
            total_gpu_vram_gb=0.0,
            network=NetworkInfo(
                interfaces=[],
                total_bandwidth_mbps=0,
                network_class="unknown",
            ),
            tier=NodeTier.CPU_PEER,
        )

    async def start(self):
        """Start the Resource Detector service."""
        if self._running:
            logger.warning("Service already running")
            return

        logger.info("Starting Resource Detector service")

        # Initial hardware detection
        await self._refresh_profile()

        # Create and start HTTP server
        self._app = await self._create_app()
        self._runner = web.AppRunner(self._app)
        await self._runner.setup()
        self._site = web.TCPSite(
            self._runner,
            self.settings["host"],
            self.settings["port"]
        )
        await self._site.start()

        self._running = True
        logger.info("Resource Detector service started",
                   host=self.settings["host"],
                   port=self.settings["port"])

    async def stop(self):
        """Stop the Resource Detector service."""
        if not self._running:
            return

        logger.info("Stopping Resource Detector service")
        self._running = False

        if self._site:
            await self._site.stop()
        if self._runner:
            await self._runner.cleanup()

        logger.info("Resource Detector service stopped")

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

            return web.json_response({
                "status": "healthy",
                "tier": self._profile.tier.value if self._profile else "unknown",
                "uptime_seconds": asyncio.get_event_loop().time() - (self._last_profile_update or 0),
            })

        # Hardware profile endpoint
        async def profile(request):
            """Get hardware profile."""
            # Refresh if cache expired
            if (self._last_profile_update and
                asyncio.get_event_loop().time() - self._last_profile_update >
                self.settings["cache_ttl_seconds"]):
                await self._refresh_profile()

            if not self._profile:
                return web.json_response(
                    {"error": "Hardware profile not available"},
                    status=503
                )

            return web.json_response({
                "tier": self._profile.tier.value,
                "cpu": {
                    "cores": self._profile.cpu.cores,
                    "threads_per_core": self._profile.cpu.threads_per_core,
                    "total_threads": self._profile.cpu.total_threads,
                    "model_name": self._profile.cpu.model_name,
                    "mhz_per_cpu": self._profile.cpu.mhz_per_cpu,
                },
                "memory": {
                    "total_mb": self._profile.memory.total_mb,
                    "total_gb": round(self._profile.memory.total_gb, 2),
                    "available_mb": self._profile.memory.available_mb,
                    "available_gb": round(self._profile.memory.available_gb, 2),
                },
                "gpus": [
                    {
                        "name": gpu.name,
                        "vram_mb": gpu.vram_mb,
                        "vram_gb": round(gpu.vram_mb / 1024, 2),
                    }
                    for gpu in self._profile.gpus
                ],
                "total_gpu_vram_gb": round(self._profile.total_gpu_vram_gb, 2),
                "network": {
                    "interfaces": self._profile.network.interfaces,
                    "total_bandwidth_mbps": self._profile.network.total_bandwidth_mbps,
                    "network_class": self._profile.network.network_class,
                },
            })

        # Resource limits endpoint
        async def limits(request):
            """Get docker-compose resource limits."""
            if not self._limits:
                return web.json_response(
                    {"error": "Resource limits not available"},
                    status=503
                )

            return web.json_response(self._limits)

        # Tier capabilities endpoint
        async def capabilities(request):
            """Get tier capabilities."""
            if not self._profile:
                return web.json_response(
                    {"error": "Hardware profile not available"},
                    status=503
                )

            from resource_detector import TIER_CAPABILITIES, get_preferred_services_for_tier

            return web.json_response({
                "tier": self._profile.tier.value,
                "capabilities": TIER_CAPABILITIES.get(self._profile.tier.value, {}),
                "preferred_services": get_preferred_services_for_tier(self._profile.tier),
            })

        # Service requirements endpoint
        async def service_requirements(request):
            """Get resource requirements for a specific service."""
            try:
                from resource_detector import SERVICE_CATEGORIES

                return web.json_response(SERVICE_CATEGORIES)
            except ImportError:
                return web.json_response({})

        app.router.add_get("/healthz", healthz)
        app.router.add_get("/readyz", healthz)  # Use same as healthz
        app.router.add_get("/profile", profile)
        app.router.add_get("/limits", limits)
        app.router.add_get("/capabilities", capabilities)
        app.router.add_get("/service-requirements", service_requirements)
        app.router.add_get("/metrics", lambda r: web.json_response({
            "service": "resource-detector",
            "tier": self._profile.tier.value if self._profile else "unknown",
        }))

        return app


async def main():
    """Main entry point for the Resource Detector service."""
    # Get settings
    settings = get_settings()

    # Configure log level
    logging.basicConfig(
        level=getattr(logging, settings["log_level"]),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    logger.info("Resource Detector service starting",
               host=settings["host"],
               port=settings["port"])

    # Create service
    service = ResourceDetectorService(settings)

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

    logger.info("Resource Detector service shutdown complete")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
        sys.exit(0)
    except Exception as e:
        logger.exception("Fatal error in Resource Detector service")
        sys.exit(1)
