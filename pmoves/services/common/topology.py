"""
Topology-aware service resolution for PMOVES.AI.

Evolves the existing DOCKED_MODE boolean into a richer topology context
that supports docked (full compose stack), hybrid (mix of compose + external),
and standalone (individual service, peers discovered dynamically) modes.

Backward-compatible: DOCKED_MODE=true → DOCKED, DOCKED_MODE=false → STANDALONE.

Network-awareness (2026-07-21, HYBRID_TOPOLOGY_NETWORK_AWARENESS.md): the context
also models the four network domains a service can live on —
  - Docker network tiers   (docker_networks; e.g. pmoves_api/app/bus/external)
  - Docker-external egress  (has_external_egress(); reaches internet + host)
  - Tailscale mesh          (tailscale; tailnet-private Serve URL if exposed)
  - Pinokio native apps     (pinokio_endpoints; host-gateway URLs)
so a service can answer "what networks am I on?" and pick the right target host.
"""

from __future__ import annotations

import json
import os
from enum import Enum
from typing import FrozenSet, Mapping, Optional

# The Docker network tier that carries internet + host egress. A service on this
# network (ideally with the highest gw-priority) can reach host.docker.internal.
EXTERNAL_NETWORK = "pmoves_external"


class TopologyMode(str, Enum):
    """Service topology mode."""

    DOCKED = "docked"          # Full compose stack, Docker DNS networking
    HYBRID = "hybrid"          # Mix compose + external (CLI Supabase, external Neo4j, etc.)
    STANDALONE = "standalone"  # Individual service, peers discovered dynamically


class TopologyContext:
    """Runtime topology context resolved from environment variables.

    Attributes:
        mode: Current topology mode
        compose_project: Docker Compose project name
        service_tier: This service's tier classification
        supabase_runtime: Supabase provider ("cli", "compose", "external")
        external_services: Set of service slugs running outside compose
        docker_networks: Docker network tiers this service is attached to
        tailscale: {node, tailnet, serve_url, tags} if tailnet-exposed, else None
        pinokio_endpoints: {app_slug: url} for native Pinokio apps this service can reach
    """

    __slots__ = (
        "mode",
        "compose_project",
        "service_tier",
        "supabase_runtime",
        "external_services",
        "docker_networks",
        "tailscale",
        "pinokio_endpoints",
    )

    def __init__(
        self,
        mode: TopologyMode,
        compose_project: str = "pmoves",
        service_tier: str = "unknown",
        supabase_runtime: str = "compose",
        external_services: FrozenSet[str] | None = None,
        docker_networks: FrozenSet[str] | None = None,
        tailscale: Optional[Mapping[str, object]] = None,
        pinokio_endpoints: Optional[Mapping[str, str]] = None,
    ) -> None:
        self.mode = mode
        self.compose_project = compose_project
        self.service_tier = service_tier
        self.supabase_runtime = supabase_runtime
        self.external_services = external_services or frozenset()
        self.docker_networks = docker_networks or frozenset()
        self.tailscale = dict(tailscale) if tailscale else None
        self.pinokio_endpoints = dict(pinokio_endpoints) if pinokio_endpoints else {}

    @classmethod
    def from_env(cls) -> TopologyContext:
        """Auto-detect topology from environment variables.

        Resolution order:
        1. TOPOLOGY_MODE explicit setting
        2. Infer from EXTERNAL_* + SUPABASE_RUNTIME + DOCKED_MODE
        """
        # Collect external service flags
        external: set[str] = set()
        if _is_true(os.environ.get("EXTERNAL_NEO4J", "")):
            external.add("neo4j")
        if _is_true(os.environ.get("EXTERNAL_MEILI", "")):
            external.add("meilisearch")
        if _is_true(os.environ.get("EXTERNAL_QDRANT", "")):
            external.add("qdrant")
        if _is_true(os.environ.get("EXTERNAL_SUPABASE", "")):
            external.add("supabase")

        supabase_runtime = os.environ.get("SUPABASE_RUNTIME", "compose").lower()
        if supabase_runtime == "cli":
            external.add("supabase")

        compose_project = os.environ.get("COMPOSE_PROJECT_NAME", "pmoves")
        service_tier = os.environ.get("SERVICE_TIER", "unknown")

        # Explicit topology mode takes priority
        topology_raw = os.environ.get("TOPOLOGY_MODE", "").lower().strip()
        if topology_raw in ("docked", "hybrid", "standalone"):
            mode = TopologyMode(topology_raw)
        elif topology_raw == "auto" or not topology_raw:
            # Auto-detect from environment signals
            mode = cls._auto_detect(external, supabase_runtime)
        else:
            # Legacy DOCKED_MODE backward compat
            docked = os.environ.get("DOCKED_MODE", "true")
            if _is_true(docked):
                mode = TopologyMode.DOCKED if not external else TopologyMode.HYBRID
            else:
                mode = TopologyMode.STANDALONE
        return cls(
            mode=mode,
            compose_project=compose_project,
            service_tier=service_tier,
            supabase_runtime=supabase_runtime,
            external_services=frozenset(external),
            docker_networks=_parse_networks(os.environ.get("PMOVES_NETWORKS", "")),
            tailscale=_parse_tailscale(),
            pinokio_endpoints=_parse_pinokio(os.environ.get("PINOKIO_ENDPOINTS", "")),
        )

    @classmethod
    def _auto_detect(
        cls,
        external: set[str],
        supabase_runtime: str,
    ) -> TopologyMode:
        """Infer topology mode from environment signals."""
        docked = os.environ.get("DOCKED_MODE", "true")

        if not _is_true(docked):
            return TopologyMode.STANDALONE

        if external or supabase_runtime == "cli":
            return TopologyMode.HYBRID

        return TopologyMode.DOCKED

    def is_external(self, service_slug: str) -> bool:
        """Check if a service is running outside the compose stack."""
        return service_slug in self.external_services

    # --- network-awareness helpers ---
    def on_network(self, network: str) -> bool:
        """True if this service is attached to the named Docker network tier."""
        return network in self.docker_networks

    def has_external_egress(self) -> bool:
        """True if this service is on the external network (internet + host reach)."""
        return EXTERNAL_NETWORK in self.docker_networks

    def is_tailnet_exposed(self) -> bool:
        """True if this service is published on the tailnet via Tailscale Serve."""
        return bool(self.tailscale and self.tailscale.get("serve_url"))

    def pinokio_url(self, slug: str) -> Optional[str]:
        """Resolve the host-gateway URL for a native Pinokio app, if reachable."""
        return self.pinokio_endpoints.get(slug)

    def resolve_host(
        self,
        slug: str,
        docker_host: str,
        external_host: str = "host.docker.internal",
    ) -> str:
        """Resolve the correct hostname for a service.

        Args:
            slug: Service slug (e.g., "supabase-db", "neo4j")
            docker_host: Docker DNS name (e.g., "supabase-db")
            external_host: External host (e.g., "host.docker.internal")

        Returns:
            Resolved hostname based on topology
        """
        if self.mode == TopologyMode.STANDALONE:
            return external_host
        if self.is_external(slug):
            return external_host
        return docker_host

    def to_dict(self) -> dict:
        """Serialize for NATS announcements, /healthz, or /topology responses."""
        return {
            "mode": self.mode.value,
            "compose_project": self.compose_project,
            "service_tier": self.service_tier,
            "supabase_runtime": self.supabase_runtime,
            "external_services": sorted(self.external_services),
            "docker_networks": sorted(self.docker_networks),
            "external_egress": self.has_external_egress(),
            "tailscale": self.tailscale or {"exposed": False},
            "pinokio_endpoints": dict(self.pinokio_endpoints),
        }

    def __repr__(self) -> str:
        return (
            f"TopologyContext(mode={self.mode.value!r}, "
            f"supabase_runtime={self.supabase_runtime!r}, "
            f"networks={sorted(self.docker_networks)}, "
            f"tailnet_exposed={self.is_tailnet_exposed()}, "
            f"external={sorted(self.external_services)})"
        )


def _is_true(value: str) -> bool:
    """Check if an env var value is truthy."""
    return value.strip().lower() in ("true", "1", "yes")


def _parse_networks(value: str) -> FrozenSet[str]:
    """Parse a comma-separated PMOVES_NETWORKS list (compose injects the service's nets)."""
    return frozenset(n.strip() for n in value.split(",") if n.strip())


def _parse_tailscale() -> Optional[dict]:
    """Build the Tailscale block from env, or None if this service isn't tailnet-exposed.

    TAILSCALE_SERVE_URL is the authoritative "I'm on the tailnet" signal; TS_NODE /
    TAILNET / TS_TAGS enrich it. A node/tailnet without a serve_url is *reachable* on
    the tailnet but not *serving* this service, so is_tailnet_exposed() stays False.
    """
    serve_url = os.environ.get("TAILSCALE_SERVE_URL", "").strip()
    node = os.environ.get("TS_NODE", "").strip()
    tailnet = os.environ.get("TAILNET", "").strip()
    tags = [t.strip() for t in os.environ.get("TS_TAGS", "").split(",") if t.strip()]
    if not (serve_url or node or tailnet or tags):
        return None
    return {"node": node or None, "tailnet": tailnet or None, "serve_url": serve_url or None, "tags": tags}


def _parse_pinokio(value: str) -> dict:
    """Parse PINOKIO_ENDPOINTS as a JSON {slug: url} map; empty/invalid → {}."""
    if not value.strip():
        return {}
    try:
        data = json.loads(value)
        return {str(k): str(v) for k, v in data.items()} if isinstance(data, dict) else {}
    except (ValueError, TypeError):
        return {}


# Module-level singleton (lazy)
_ctx: TopologyContext | None = None


def get_topology() -> TopologyContext:
    """Get the current topology context (cached singleton)."""
    global _ctx
    if _ctx is None:
        _ctx = TopologyContext.from_env()
    return _ctx


def reset_topology() -> None:
    """Reset cached topology (for testing)."""
    global _ctx
    _ctx = None
