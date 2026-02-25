"""
Topology-aware service resolution for PMOVES.AI.

Evolves the existing DOCKED_MODE boolean into a richer topology context
that supports docked (full compose stack), hybrid (mix of compose + external),
and standalone (individual service, peers discovered dynamically) modes.

Backward-compatible: DOCKED_MODE=true → DOCKED, DOCKED_MODE=false → STANDALONE.
"""

from __future__ import annotations

import os
from enum import Enum
from typing import FrozenSet


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
    """

    __slots__ = (
        "mode",
        "compose_project",
        "service_tier",
        "supabase_runtime",
        "external_services",
    )

    def __init__(
        self,
        mode: TopologyMode,
        compose_project: str = "pmoves",
        service_tier: str = "unknown",
        supabase_runtime: str = "compose",
        external_services: FrozenSet[str] | None = None,
    ) -> None:
        self.mode = mode
        self.compose_project = compose_project
        self.service_tier = service_tier
        self.supabase_runtime = supabase_runtime
        self.external_services = external_services or frozenset()

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
        """Serialize for NATS announcements or API responses."""
        return {
            "mode": self.mode.value,
            "compose_project": self.compose_project,
            "service_tier": self.service_tier,
            "supabase_runtime": self.supabase_runtime,
            "external_services": sorted(self.external_services),
        }

    def __repr__(self) -> str:
        return (
            f"TopologyContext(mode={self.mode.value!r}, "
            f"supabase_runtime={self.supabase_runtime!r}, "
            f"external={sorted(self.external_services)})"
        )


def _is_true(value: str) -> bool:
    """Check if an env var value is truthy."""
    return value.strip().lower() in ("true", "1", "yes")


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
