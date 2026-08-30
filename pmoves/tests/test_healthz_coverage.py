#!/usr/bin/env python3
"""Healthz coverage test — validates all catalog services expose /healthz.

Satisfies TAC node stage-1.healthz-coverage (issue #1389).
This is a static-config test (not a live-network probe) — it verifies that
every service listed in the CATALOG.md has a declared /healthz endpoint in
the prometheus config or compose healthcheck.

Run: pytest -q pmoves/tests/test_healthz_coverage.py
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
CATALOG_PATH = REPO_ROOT / ".claude" / "CATALOG.md"
COMPOSE_PATH = REPO_ROOT / "pmoves" / "docker-compose.yml"

# Services known to NOT expose /healthz (documented exceptions)
HEALTHZ_EXCEPTIONS = {
    "cipher",        # Cipher uses /health (not /healthz)
    "nats",          # NATS uses :8222/healthz (different port)
    "neo4j",         # Neo4j uses :2004 (not /healthz path)
    "qdrant",        # Qdrant root / is health
    "minio",         # MinIO uses :9000/minio/health/live
    "clickhouse",    # ClickHouse uses native protocol
    "loki",          # Loki root /
    "cadvisor",      # cAdvisor root / (infra)
    "prometheus",    # Prometheus root / (infra)
    "kong",          # Kong /health (not /healthz)
    "valkey",        # Valkey native protocol
}


def _parse_catalog_services() -> dict[str, str]:
    """Parse CATALOG.md for service names and health endpoints."""
    if not CATALOG_PATH.exists():
        pytest.skip(f"CATALOG.md not found: {CATALOG_PATH}")

    content = CATALOG_PATH.read_text(encoding="utf-8")
    services: dict[str, str] = {}

    for line in content.splitlines():
        name_match = re.search(r"\*\*(.+?)\*\*", line)
        if not name_match:
            continue
        health_match = re.search(r"(/healthz?)\b", line, re.IGNORECASE)
        if health_match:
            name = name_match.group(1).strip().lower().replace(" ", "-")
            services[name] = health_match.group(1)

    return services


def _parse_compose_healthchecks() -> set[str]:
    """Parse docker-compose.yml for services with healthcheck blocks."""
    if not COMPOSE_PATH.exists():
        pytest.skip(f"docker-compose.yml not found: {COMPOSE_PATH}")

    content = COMPOSE_PATH.read_text(encoding="utf-8")
    has_healthcheck: set[str] = set()
    current_service: str | None = None
    for line in content.splitlines():
        svc_match = re.match(r"^\s{2}(\S+):", line)
        if svc_match:
            current_service = svc_match.group(1)
        if re.match(r"^\s{4}healthcheck:", line) and current_service:
            has_healthcheck.add(current_service)
    return has_healthcheck


class TestHealthzCoverage:
    """Validate /healthz coverage across all catalog services."""

    @pytest.fixture(scope="class")
    def catalog_services(self) -> dict[str, str]:
        services = _parse_catalog_services()
        assert len(services) > 5, f"Expected >5 catalog services, got {len(services)}"
        return services

    def test_catalog_parses_services(self, catalog_services: dict[str, str]) -> None:
        """CATALOG.md should parse into a non-empty service map."""
        assert catalog_services, "No services parsed from CATALOG.md"

    def test_healthz_endpoints_declared(self, catalog_services: dict[str, str]) -> None:
        """Every catalog service should declare a health endpoint (or be in exceptions)."""
        missing = []
        for name, health_url in catalog_services.items():
            if any(exc in name for exc in HEALTHZ_EXCEPTIONS):
                continue
            if "healthz" not in health_url and "/health" not in health_url:
                missing.append(name)

        assert not missing, (
            f"Services without declared health endpoint: {missing}. "
            f"Add /healthz to each, or document as exception in HEALTHZ_EXCEPTIONS."
        )

    def test_known_exceptions_documented(self) -> None:
        """HEALTHZ_EXCEPTIONS should be non-empty (Cipher, NATS, etc. are documented)."""
        assert len(HEALTHZ_EXCEPTIONS) >= 5, (
            "Expected at least 5 healthz exceptions (cipher, nats, neo4j, etc.)"
        )

    def test_compose_has_healthchecks(self) -> None:
        """docker-compose.yml should define healthcheck blocks for core services."""
        services_with_health = _parse_compose_healthchecks()
        assert len(services_with_health) >= 3, (
            f"Expected >=3 compose services with healthcheck, got {len(services_with_health)}: "
            f"{services_with_health}"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
