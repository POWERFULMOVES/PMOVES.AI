"""
PMOVES.AI Service Registry

Central service discovery registry for multi-host PMOVES.AI deployments.
Enables services running standalone (e.g., PMOVES-DoX on Jetson) to be
discoverable by PMOVES.AI on PC and vice versa.

Features:
- Service registration via HTTP API
- Health check monitoring
- Multi-host mesh network support (Tailscale)
- NATS-based announcements
- Service capability discovery
"""
import asyncio
import contextlib
import json
import logging
import os
import time
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set
from dataclasses import dataclass, asdict, field

import fastapi
import uvicorn
from fastapi import FastAPI, HTTPException, Query, Body
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import nats

# Configuration
REGISTRY_PORT = int(os.getenv("SERVICE_REGISTRY_PORT", "8100"))
REGISTRY_HOST = os.getenv("SERVICE_REGISTRY_HOST", "0.0.0.0")
NATS_URL = os.getenv("NATS_URL", "nats://nats:4222")
NATS_EXTERNAL_URL = os.getenv("NATS_EXTERNAL_URL", "")
MESH_HOSTNAME = os.getenv("MESH_HOSTNAME", "")
MESH_NAME = os.getenv("PMOVES_MESH_NAME", "pmoves-mesh")

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("service-registry")


class ServiceMode(str, Enum):
    """Service deployment mode."""
    STANDALONE = "standalone"  # Running independently
    DOCKED = "docked"          # Integrated with PMOVES.AI


class HealthStatus(str, Enum):
    """Service health status."""
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class ServiceInfo:
    """Information about a registered service."""
    name: str
    host: str  # IP or hostname
    port: int
    mode: ServiceMode
    capabilities: List[str] = field(default_factory=list)
    health_url: Optional[str] = None
    health_status: HealthStatus = HealthStatus.UNKNOWN
    last_seen: datetime = field(default_factory=datetime.utcnow)
    registered_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        data["last_seen"] = self.last_seen.isoformat()
        data["registered_at"] = self.registered_at.isoformat()
        data["mode"] = self.mode.value
        data["health_status"] = self.health_status.value
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ServiceInfo":
        """Create from dictionary."""
        if "last_seen" in data and isinstance(data["last_seen"], str):
            data["last_seen"] = datetime.fromisoformat(data["last_seen"])
        if "registered_at" in data and isinstance(data["registered_at"], str):
            data["registered_at"] = datetime.fromisoformat(data["registered_at"])
        if "mode" in data and isinstance(data["mode"], str):
            data["mode"] = ServiceMode(data["mode"])
        if "health_status" in data and isinstance(data["health_status"], str):
            data["health_status"] = HealthStatus(data["health_status"])
        return cls(**data)


class ServiceRegistry:
    """Central service registry for PMOVES.AI."""

    def __init__(self):
        self.services: Dict[str, ServiceInfo] = {}
        self.nc: Optional[nats.aio.client.Client] = None
        self.js: Optional[nats.aio.jetstream.JetStreamContext] = None
        self._health_check_interval = 30
        self._service_timeout_seconds = 300  # 5 minutes

    async def setup_nats(self):
        """Connect to NATS and setup JetStream."""
        try:
            logger.info(f"Connecting to NATS at {NATS_URL}")
            self.nc = await nats.connect(NATS_URL)
            self.js = self.nc.jetstream()

            # Create JetStream for service events
            await self.js.add_stream(
                name="service_registry",
                subjects=["service.registry.>"],
                description="Service registry events"
            )

            # Subscribe to service announcements
            await self.nc.subscribe(
                "mesh.node.announce.v1",
                cb=self._handle_announcement
            )

            # Subscribe to health updates
            await self.nc.subscribe(
                "service.health.>",
                cb=self._handle_health_update
            )

            # Announce registry presence
            await self.announce_registry()

            logger.info("NATS connection established")

        except Exception as e:
            logger.error(f"Failed to setup NATS: {e}")

    async def announce_registry(self):
        """Announce the service registry to the mesh."""
        announcement = {
            "type": "service.registry",
            "name": "service-registry",
            "host": os.getenv("HOSTNAME", "localhost"),
            "port": REGISTRY_PORT,
            "capabilities": ["registry", "discovery"],
            "ts": int(time.time())
        }

        if self.nc:
            await self.nc.publish(
                "mesh.node.announce.v1",
                json.dumps(announcement).encode()
            )
            logger.info("Service registry announced to mesh")

    async def _handle_announcement(self, msg):
        """Handle incoming mesh node announcements."""
        try:
            data = json.loads(msg.data.decode())

            # Extract service info from announcement
            if data.get("type") == "mesh.node.announce.v1":
                node = data.get("node", data.get("name", ""))
                caps = data.get("caps", data.get("capabilities", []))
                host = data.get("host", "")
                port = data.get("port", 0)

                if node and host:
                    await self.register(
                        name=node,
                        host=host,
                        port=port,
                        mode=ServiceMode.STANDALONE,
                        capabilities=caps if isinstance(caps, list) else [],
                        metadata={"source": "nats_announcement"}
                    )

        except Exception as e:
            logger.error(f"Error handling announcement: {e}")

    async def _handle_health_update(self, msg):
        """Handle incoming health update messages."""
        try:
            data = json.loads(msg.data.decode())
            service_name = data.get("service")
            status = HealthStatus(data.get("status", "unknown"))

            if service_name and service_name in self.services:
                self.services[service_name].health_status = status
                self.services[service_name].last_seen = datetime.utcnow()

        except Exception as e:
            logger.error(f"Error handling health update: {e}")

    async def register(
        self,
        name: str,
        host: str,
        port: int,
        mode: ServiceMode = ServiceMode.STANDALONE,
        capabilities: Optional[List[str]] = None,
        health_url: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ServiceInfo:
        """Register a new service or update existing."""
        now = datetime.utcnow()

        if name in self.services:
            # Update existing service
            service = self.services[name]
            service.host = host
            service.port = port
            service.mode = mode
            service.last_seen = now
            if capabilities:
                service.capabilities = capabilities
            if health_url:
                service.health_url = health_url
            if metadata:
                service.metadata.update(metadata)
            logger.info(f"Updated service: {name}")
        else:
            # Register new service
            service = ServiceInfo(
                name=name,
                host=host,
                port=port,
                mode=mode,
                capabilities=capabilities or [],
                health_url=health_url,
                metadata=metadata or {}
            )
            self.services[name] = service
            logger.info(f"Registered service: {name} at {host}:{port}")

        # Publish registration event
        await self._publish_event("registered", name, service.to_dict())

        return service

    async def unregister(self, name: str) -> bool:
        """Unregister a service."""
        if name in self.services:
            del self.services[name]
            await self._publish_event("unregistered", name, {"name": name})
            logger.info(f"Unregistered service: {name}")
            return True
        return False

    async def get_service(self, name: str) -> Optional[ServiceInfo]:
        """Get a service by name."""
        return self.services.get(name)

    async def list_services(
        self,
        mode: Optional[ServiceMode] = None,
        capability: Optional[str] = None,
        healthy_only: bool = False
    ) -> List[Dict[str, Any]]:
        """List all registered services with optional filtering."""
        services = []

        for service in self.services.values():
            # Filter by mode
            if mode and service.mode != mode:
                continue

            # Filter by capability
            if capability and capability not in service.capabilities:
                continue

            # Filter by health
            if healthy_only and service.health_status != HealthStatus.HEALTHY:
                continue

            # Check timeout
            if (datetime.utcnow() - service.last_seen).total_seconds() > self._service_timeout_seconds:
                continue

            services.append(service.to_dict())

        return services

    async def discover(self, capabilities: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Discover services by capabilities."""
        all_services = await self.list_services()

        if not capabilities:
            return all_services

        # Find services with ALL requested capabilities
        matching = []
        for service in all_services:
            if all(cap in service["capabilities"] for cap in capabilities):
                matching.append(service)

        return matching

    async def _publish_event(self, event_type: str, service_name: str, data: Dict[str, Any]):
        """Publish a service registry event to NATS."""
        if not self.nc:
            return

        event = {
            "type": event_type,
            "service": service_name,
            "timestamp": datetime.utcnow().isoformat(),
            "data": data
        }

        await self.nc.publish(
            f"service.registry.{event_type}",
            json.dumps(event).encode()
        )

    async def health_check_loop(self):
        """Background task to check service health."""
        import aiohttp

        while True:
            await asyncio.sleep(self._health_check_interval)

            for name, service in self.services.items():
                if not service.health_url:
                    continue

                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(
                            service.health_url,
                            timeout=aiohttp.ClientTimeout(total=5)
                        ) as resp:
                            if resp.status == 200:
                                service.health_status = HealthStatus.HEALTHY
                            else:
                                service.health_status = HealthStatus.UNHEALTHY
                except Exception as e:
                    logger.debug(f"Health check failed for {name}: {e}")
                    service.health_status = HealthStatus.UNHEALTHY

    async def cleanup_loop(self):
        """Background task to remove stale services."""
        while True:
            await asyncio.sleep(60)  # Check every minute

            now = datetime.utcnow()
            stale_services = []

            for name, service in self.services.items():
                age_seconds = (now - service.last_seen).total_seconds()
                if age_seconds > self._service_timeout_seconds:
                    stale_services.append(name)

            for name in stale_services:
                await self.unregister(name)
                logger.info(f"Removed stale service: {name}")


# Global registry (must be initialized before lifespan)
registry = ServiceRegistry()


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown events."""
    # Startup
    await registry.setup_nats()

    # Start background tasks
    asyncio.create_task(registry.health_check_loop())
    asyncio.create_task(registry.cleanup_loop())

    logger.info("Service Registry started")

    yield

    # Shutdown
    if registry.nc:
        await registry.nc.close()
    logger.info("Service Registry stopped")


# FastAPI app
app = FastAPI(
    title="PMOVES.AI Service Registry",
    description="Central service discovery for multi-host PMOVES.AI deployments",
    version="1.0.0",
    lifespan=lifespan
)


# Pydantic models for API
class ServiceRegister(BaseModel):
    name: str = Field(..., description="Service name")
    host: str = Field(..., description="Service host (IP or hostname)")
    port: int = Field(..., ge=1, le=65535, description="Service port")
    mode: ServiceMode = Field(default=ServiceMode.STANDALONE, description="Deployment mode")
    capabilities: List[str] = Field(default_factory=list, description="Service capabilities")
    health_url: Optional[str] = Field(None, description="Health check URL")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class HealthResponse(BaseModel):
    status: str
    registry: Dict[str, Any]
    services: int


# API Endpoints
@app.get("/healthz")
async def health():
    """Health check endpoint."""
    return {"status": "healthy", "service": "service-registry"}


@app.get("/")
async def root():
    """Root endpoint with registry info."""
    return {
        "name": "PMOVES.AI Service Registry",
        "version": "1.0.0",
        "mesh": MESH_NAME,
        "hostname": MESH_HOSTNAME,
        "services": len(registry.services),
        "endpoints": {
            "register": "POST /api/services",
            "list": "GET /api/services",
            "get": "GET /api/services/{name}",
            "discover": "POST /api/discover",
            "health": "GET /healthz"
        }
    }


@app.post("/api/services")
async def register_service(service: ServiceRegister):
    """Register or update a service."""
    result = await registry.register(
        name=service.name,
        host=service.host,
        port=service.port,
        mode=service.mode,
        capabilities=service.capabilities,
        health_url=service.health_url,
        metadata=service.metadata
    )
    return {"status": "registered", "service": result.to_dict()}


@app.delete("/api/services/{name}")
async def unregister_service(name: str):
    """Unregister a service."""
    success = await registry.unregister(name)
    if not success:
        raise HTTPException(status_code=404, detail="Service not found")
    return {"status": "unregistered", "name": name}


@app.get("/api/services")
async def list_services(
    mode: Optional[str] = Query(None, description="Filter by mode (standalone/docked)"),
    capability: Optional[str] = Query(None, description="Filter by capability"),
    healthy_only: bool = Query(False, description="Only return healthy services")
):
    """List all registered services with optional filtering."""
    services = await registry.list_services(
        mode=ServiceMode(mode) if mode else None,
        capability=capability,
        healthy_only=healthy_only
    )
    return {
        "count": len(services),
        "services": services
    }


@app.get("/api/services/{name}")
async def get_service(name: str):
    """Get a specific service by name."""
    service = await registry.get_service(name)
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    return service.to_dict()


@app.post("/api/discover")
async def discover_services(
    capabilities: Optional[List[str]] = Body(None, description="Required capabilities")
):
    """Discover services by capabilities."""
    services = await registry.discover(capabilities)
    return {
        "count": len(services),
        "services": services
    }


@app.get("/api/status")
async def registry_status():
    """Get registry status."""
    return {
        "registry": {
            "mesh": MESH_NAME,
            "hostname": MESH_HOSTNAME,
            "nats_url": NATS_URL,
            "nats_external": NATS_EXTERNAL_URL,
            "services": len(registry.services)
        },
        "services": await registry.list_services()
    }


def main():
    """Run the service registry."""
    uvicorn.run(
        "app:app",
        host=REGISTRY_HOST,
        port=REGISTRY_PORT,
        log_level="info"
    )


if __name__ == "__main__":
    main()
