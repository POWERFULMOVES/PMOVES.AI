"""
Dynamic port resolution bridging port_allocator defaults with topology context.

Resolves the correct (host, port) tuple for any service based on:
1. Environment variable overrides ({SLUG}_HOST_PORT, {SLUG}_URL)
2. port_allocator.DEFAULT_PORTS registry
3. Topology-aware host selection (Docker DNS vs external)
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Tuple

# Add scripts dir so we can import port_allocator
_scripts_dir = str(Path(__file__).resolve().parents[2] / "scripts")
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

try:
    from port_allocator import DEFAULT_PORTS
except ImportError:
    DEFAULT_PORTS = {}

from services.common.topology import TopologyContext, TopologyMode, get_topology


# Docker DNS names for services (slug → container hostname)
DOCKER_DNS_MAP: dict[str, str] = {
    "supabase-db": "supabase-db",
    "supabase-postgrest": "supabase-postgrest",
    "supabase-gotrue": "supabase-gotrue",
    "supabase-kong": "supabase-kong",
    "supabase-storage": "supabase-storage",
    "nats": "nats",
    "neo4j": "neo4j",
    "meilisearch": "meilisearch",
    "qdrant": "qdrant",
    "minio": "minio",
    "hi-rag-gateway-v2": "hi-rag-gateway-v2",
    "hi-rag-gateway-v2-gpu": "hi-rag-gateway-v2-gpu",
    "agent-zero": "agent-zero",
    "archon": "archon",
    "tensorzero-gateway": "tensorzero-gateway",
    "extract-worker": "extract-worker",
    "pmoves-yt": "pmoves-yt",
    "flute-gateway": "flute-gateway",
    "deepresearch": "deepresearch",
    "supaserch": "supaserch",
}

# External (host-mapped) ports — used when services run outside compose
# Maps slug → the host port that's mapped in docker-compose.yml
EXTERNAL_PORT_MAP: dict[str, str] = {
    "supabase-db": "SUPABASE_DB_PORT",
    "supabase-postgrest": "SUPABASE_POSTGREST_PORT",
    "supabase-kong": "SUPABASE_KONG_PROXY_PORT",
    "neo4j": "NEO4J_HTTP_HOST_PORT",
    "meilisearch": "MEILI_HOST_PORT",
    "qdrant": "QDRANT_HOST_PORT",
    "minio": "MINIO_HOST_PORT",
    "nats": "NATS_HOST_PORT",
}


class PortResolver:
    """Resolve service host:port based on topology and env overrides."""

    def __init__(self, topology: TopologyContext | None = None) -> None:
        self.topology = topology or get_topology()

    def resolve(self, slug: str) -> Tuple[str, int]:
        """Resolve the (host, port) for a service.

        Returns:
            (hostname, port) tuple
        """
        # 1. Check explicit env override
        env_key = slug.upper().replace("-", "_") + "_HOST_PORT"
        env_port = os.environ.get(env_key, "").strip()

        # 2. Get default port from allocator
        default_port = DEFAULT_PORTS.get(slug, 0)

        # 3. Determine host based on topology
        docker_host = DOCKER_DNS_MAP.get(slug, slug)
        external_host = os.environ.get("EXTERNAL_HOST", "host.docker.internal")

        if self.topology.is_external(slug) or self.topology.mode == TopologyMode.STANDALONE:
            host = external_host
            # For external services, use the mapped host port
            if env_port:
                port = int(env_port)
            else:
                ext_port_key = EXTERNAL_PORT_MAP.get(slug, "")
                ext_port = os.environ.get(ext_port_key, "").strip() if ext_port_key else ""
                port = int(ext_port) if ext_port else default_port
        else:
            host = docker_host
            port = int(env_port) if env_port else default_port

        return host, port

    def resolve_url(self, slug: str, scheme: str = "http") -> str:
        """Resolve full URL for a service.

        Returns:
            URL like "http://supabase-db:5432"
        """
        host, port = self.resolve(slug)
        if port:
            return f"{scheme}://{host}:{port}"
        return f"{scheme}://{host}"

    def resolve_all(self) -> dict[str, Tuple[str, int]]:
        """Resolve all known services.

        Returns:
            Dict of slug → (host, port)
        """
        all_slugs = set(DEFAULT_PORTS.keys()) | set(DOCKER_DNS_MAP.keys())
        return {slug: self.resolve(slug) for slug in sorted(all_slugs) if DEFAULT_PORTS.get(slug, 0) > 0}


def main() -> int:
    """CLI entry point — display port resolution map."""
    resolver = PortResolver()
    topo = resolver.topology

    print(f"Topology: {topo.mode.value}")
    print(f"  Compose project: {topo.compose_project}")
    print(f"  Supabase runtime: {topo.supabase_runtime}")
    if topo.external_services:
        print(f"  External services: {', '.join(sorted(topo.external_services))}")
    print()

    resolved = resolver.resolve_all()
    print(f"{'Service':<30} {'Host':<30} {'Port':<8}")
    print("-" * 70)
    for slug, (host, port) in resolved.items():
        print(f"{slug:<30} {host:<30} {port:<8}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
