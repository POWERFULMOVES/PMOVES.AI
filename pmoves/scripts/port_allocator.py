#!/usr/bin/env python3
"""
PMOVES.AI Port Allocator

Intelligently assigns ports to services to avoid conflicts.
Supports three strategies:
1. Dynamic - Docker assigns ports (host port 0)
2. Hybrid - Default ports with environment override
3. Auto - First-run detection and persistence

Usage:
    python3 scripts/port_allocator.py --strategy auto
    python3 scripts/port_allocator.py --validate
    python3 scripts/port_allocator.py --assign agent-zero 8080
"""
import argparse
import json
import os
import socket
import sys
from pathlib import Path
from typing import Dict, List, Optional


# Default port assignments for PMOVES.AI services
DEFAULT_PORTS = {
    # Core Infrastructure
    "nats": 4222,
    "nats-monitoring": 8222,
    "postgres": 5432,
    "supabase-db": 5432,
    "postgrest": 3010,
    "qdrant": 6333,
    "qdrant-dashboard": 6333,
    "neo4j": 7474,
    "meilisearch": 7700,
    "minio": 9000,
    "minio-console": 9001,
    "clickhouse": 8123,
    "tensorzero-gateway": 3030,
    "tensorzero-ui": 4000,
    "prometheus": 9090,
    "grafana": 3000,
    "loki": 3100,
    "surrealdb": 8000,

    # Agent & Orchestration
    "agent-zero": 8080,
    "agent-zero-ui": 8081,
    "archon": 8091,
    "archon-ui": 3737,
    "mesh-agent": 0,  # No HTTP interface
    "service-registry": 8100,

    # Retrieval & Knowledge
    "hi-rag-gateway-v2": 8086,
    "hi-rag-gateway-v2-gpu": 8087,
    "deepresearch": 8098,
    "supaserch": 8099,

    # Voice & Speech
    "flute-gateway": 8055,
    "flute-gateway-ws": 8056,
    "ultimate-tts-studio": 7861,

    # Media Ingestion
    "pmoves-yt": 8077,
    "ffmpeg-whisper": 8078,
    "media-video": 8079,
    "media-audio": 8082,
    "extract-worker": 8083,
    "pdf-ingest": 8092,
    "langextract": 8084,
    "notebook-sync": 8095,

    # Integration
    "presign": 8088,
    "render-webhook": 8085,
    "publisher-discord": 8094,
    "jellyfin-bridge": 8093,
    "n8n": 5678,
    "botz-gateway": 8090,
}

# Port ranges to avoid
RESERVED_RANGES = [
    (0, 1024),      # Well-known ports
    (6881, 6889),   # BitTorrent
    (8333, 8333),   # Bitcoin
]

# Port allocation range for dynamic assignment
DYNAMIC_PORT_RANGE = (10000, 11000)


def is_port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    """Check if a port is in use on the specified host."""
    if port <= 0:
        return False
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            result = s.connect_ex((host, port))
            return result == 0
    except Exception:
        return False


def is_port_reserved(port: int) -> bool:
    """Check if port falls in a reserved range."""
    for start, end in RESERVED_RANGES:
        if start <= port <= end:
            return True
    return False


def find_available_port(start: int, end: int = None) -> Optional[int]:
    """Find an available port in the specified range."""
    if end is None:
        end = start + 100

    for port in range(start, end + 1):
        if not is_port_reserved(port) and not is_port_in_use(port):
            return port
    return None


class PortAllocator:
    """Manages port allocation for PMOVES.AI services."""

    def __init__(self, ports_file: Optional[Path] = None):
        self.ports_file = ports_file or Path(__file__).parent.parent / "data" / "ports.json"
        self.ports: Dict[str, int] = {}
        self._load_ports()

    def _load_ports(self):
        """Load port assignments from file."""
        if self.ports_file.exists():
            try:
                with open(self.ports_file) as f:
                    self.ports = json.load(f)
            except (json.JSONDecodeError, IOError):
                self.ports = {}

    def _save_ports(self):
        """Save port assignments to file."""
        self.ports_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.ports_file, "w") as f:
            json.dump(self.ports, f, indent=2)

    def get_port(self, service: str, default: Optional[int] = None) -> int:
        """Get the assigned port for a service."""
        if service in self.ports:
            return self.ports[service]

        if default is None:
            default = DEFAULT_PORTS.get(service, 0)

        if default and not is_port_in_use(default):
            self.ports[service] = default
            self._save_ports()
            return default

        # Find an available port
        assigned = self.assign_port(service)
        return assigned if assigned else default

    def assign_port(self, service: str, port: Optional[int] = None) -> Optional[int]:
        """Assign a specific port to a service, or auto-allocate."""
        if port is not None:
            if is_port_in_use(port):
                raise ValueError(f"Port {port} is already in use")
            self.ports[service] = port
            self._save_ports()
            return port

        # Auto-allocate from dynamic range
        start, end = DYNAMIC_PORT_RANGE
        for attempt_port in range(start, end + 1):
            if not is_port_in_use(attempt_port) and attempt_port not in self.ports.values():
                self.ports[service] = attempt_port
                self._save_ports()
                return attempt_port

        return None

    def validate_ports(self) -> List[str]:
        """Validate current port assignments for conflicts."""
        conflicts = []

        # Check for duplicate ports
        port_to_services: Dict[int, List[str]] = {}
        for service, port in self.ports.items():
            port_to_services.setdefault(port, []).append(service)

        for port, services in port_to_services.items():
            if len(services) > 1:
                conflicts.append(f"Port {port} used by multiple services: {', '.join(services)}")

        # Check for ports in use
        for service, port in self.ports.items():
            if is_port_in_use(port):
                # Check if the service is actually running
                conflicts.append(f"Port {port} for {service} is in use by another process")

        return conflicts

    def detect_and_assign(self) -> Dict[str, int]:
        """Detect port conflicts and reassign as needed."""
        reassigned = {}

        for service, default_port in DEFAULT_PORTS.items():
            if default_port == 0:
                continue  # Skip services without HTTP interfaces

            current = self.ports.get(service, default_port)

            if is_port_in_use(current) and not self._is_service_running(service, current):
                # Find new port
                new_port = find_available_port(DYNAMIC_PORT_RANGE[0], DYNAMIC_PORT_RANGE[1])
                if new_port:
                    self.ports[service] = new_port
                    reassigned[service] = {"old": current, "new": new_port}

        if reassigned:
            self._save_ports()

        return reassigned

    def _is_service_running(self, service: str, port: int) -> bool:
        """Check if the actual service is running on the port."""
        # Simple heuristic - could be enhanced with actual service checks
        return is_port_in_use(port)

    def generate_env_override(self) -> str:
        """Generate environment variable overrides for assigned ports."""
        lines = []
        for service, port in self.ports.items():
            if port > 0:
                env_name = f"{service.upper().replace('-', '_')}_HOST_PORT"
                lines.append(f"{env_name}={port}")
        return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="PMOVES.AI Port Allocator")
    parser.add_argument("--strategy", choices=["dynamic", "hybrid", "auto"],
                       default="auto", help="Port allocation strategy")
    parser.add_argument("--validate", action="store_true",
                       help="Validate current port assignments")
    parser.add_argument("--assign", nargs=2, metavar=("SERVICE", "PORT"),
                       help="Assign a specific port to a service")
    parser.add_argument("--get", metavar="SERVICE",
                       help="Get the port for a specific service")
    parser.add_argument("--detect", action="store_true",
                       help="Detect conflicts and reassign ports")
    parser.add_argument("--env-overrides", action="store_true",
                       help="Generate environment variable overrides")
    parser.add_argument("--ports-file", type=Path,
                       help="Path to ports.json file")

    args = parser.parse_args()
    allocator = PortAllocator(args.ports_file)

    if args.validate:
        conflicts = allocator.validate_ports()
        if conflicts:
            print("Port conflicts detected:")
            for conflict in conflicts:
                print(f"  - {conflict}")
            sys.exit(1)
        else:
            print("No port conflicts detected.")
            sys.exit(0)

    elif args.assign:
        service, port = args.assign
        try:
            assigned = allocator.assign_port(service, int(port))
            print(f"Assigned port {assigned} to {service}")
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)

    elif args.get:
        port = allocator.get_port(args.get)
        print(f"{args.get}: {port}")

    elif args.detect:
        reassigned = allocator.detect_and_assign()
        if reassigned:
            print("Reassigned ports:")
            for service, ports in reassigned.items():
                print(f"  {service}: {ports['old']} -> {ports['new']}")
        else:
            print("No conflicts detected. All ports are OK.")

    elif args.env_overrides:
        print(allocator.generate_env_override())

    else:
        # Default: show current assignments
        print("Current port assignments:")
        for service, port in sorted(allocator.ports.items()):
            status = "in use" if is_port_in_use(port) else "free"
            print(f"  {service}: {port} ({status})")


if __name__ == "__main__":
    main()
