#!/usr/bin/env python3
"""Service health checker using PMOVES service discovery.

Supports hybrid operation:
- Docked: Uses NATS/Supabase service discovery
- Standalone: Falls back to Docker DNS (service-name:port)

Usage:
    python3 tools/service_health_check.py hirag-v2 --port 8086
    export SERVICE_HIRAG_V2_URL=http://localhost:8086  # Override
"""

import argparse
import os
import sys
from pathlib import Path

# Add services to path
_services_root = Path(__file__).parent.parent
sys.path.insert(0, str(_services_root))

try:
    from services.common.service_registry import get_service_url_sync
    SERVICE_REGISTRY_AVAILABLE = True
except ImportError:
    SERVICE_REGISTRY_AVAILABLE = False


def get_service_url_cli(slug: str, default_port: int = 80) -> str:
    """CLI wrapper for service URL resolution with fallback.

    Priority:
    1. Environment variable (SERVICE_<NAME>_URL) - Works in all modes
    2. Service registry (NATS/Supabase/Docker DNS) - Docked mode
    3. Docker DNS fallback - Works in docker compose (standalone)

    Args:
        slug: Service slug (e.g., hirag-v2, agent-zero, archon)
        default_port: Default port if not discovered

    Returns:
        Resolved service URL (e.g., http://hirag-v2:8086)
    """
    # 1. Environment override (works in all modes)
    # Convert slug to env var format: hirag-v2 -> HIRAG_V2
    env_var = "SERVICE_" + slug.upper().replace("-", "_")
    url = os.environ.get(env_var)
    if url:
        return url

    # 2. Service registry (dockered mode with NATS/Supabase)
    if SERVICE_REGISTRY_AVAILABLE:
        try:
            return get_service_url_sync(slug, default_port=default_port)
        except Exception:
            pass  # Fall through to Docker DNS

    # 3. Docker DNS fallback (works in standalone with docker compose)
    return f"http://{slug}:{default_port}"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Resolve service URL using PMOVES service discovery",
        epilog="Supports docked (NATS/Supabase) and standalone (Docker DNS) modes"
    )
    parser.add_argument("slug", help="Service slug (e.g., hirag-v2, agent-zero, archon)")
    parser.add_argument("--port", type=int, default=80, help="Default port (default: 80)")
    args = parser.parse_args()

    print(get_service_url_cli(args.slug, args.port), end="")
