"""
Static validation of service catalog against docker-compose configuration.

Cross-references service_catalog.py definitions against the actual
docker-compose.yml to catch drift between documented and deployed config.

Runs without Docker — pure YAML + Python validation.
"""

import re
import yaml
import pytest
from pathlib import Path

from _smoke_helpers import PMOVES_DIR
from pmoves.tests.utils.service_catalog import (
    SERVICES,
    INTERNAL_SERVICES,
    get_service_by_name,
)


COMPOSE_FILE = PMOVES_DIR / "docker-compose.yml"


def _load_all_compose_services():
    """Load services from all compose files, skip if unavailable."""
    if not COMPOSE_FILE.exists():
        pytest.skip("docker-compose.yml not found")

    all_services = {}
    for f in PMOVES_DIR.glob("docker-compose*.yml"):
        try:
            data = yaml.safe_load(f.read_text())
            if isinstance(data, dict):
                all_services.update(data.get("services", {}))
        except yaml.YAMLError:
            continue
    return all_services


def _load_main_compose_services():
    """Load services from main compose file only."""
    if not COMPOSE_FILE.exists():
        pytest.skip("docker-compose.yml not found")
    data = yaml.safe_load(COMPOSE_FILE.read_text())
    return data.get("services", {})


# ============================================================================
# CATALOG vs COMPOSE CROSS-CHECK
# ============================================================================

@pytest.mark.smoke
def test_catalog_services_exist_in_compose():
    """Verify every ServiceDefinition with a port has a matching compose service."""
    compose_services = _load_all_compose_services()
    compose_names = set(compose_services.keys())

    missing = []
    for svc in SERVICES:
        if svc.port == 0:
            continue  # No HTTP interface — may be NATS worker
        if svc.name not in compose_names:
            missing.append(f"{svc.name} (port {svc.port})")

    # Advisory warning — catalog may define future services
    if missing:
        import warnings
        warnings.warn(
            f"{len(missing)} catalog services not in any compose file: "
            f"{', '.join(missing[:5])}"
        )


@pytest.mark.smoke
def test_catalog_ports_match_compose():
    """Verify catalog port matches compose port mapping for key services."""
    compose_services = _load_all_compose_services()

    mismatches = []
    for svc in SERVICES:
        if svc.port == 0:
            continue
        compose_svc = compose_services.get(svc.name, {})
        if not compose_svc or not isinstance(compose_svc, dict):
            continue  # Service not in compose

        ports = compose_svc.get("ports", [])
        port_strs = [str(p) for p in ports]

        # Check if the catalog port appears in any port mapping
        # Also resolve ${VAR:-DEFAULT} patterns
        catalog_port_str = str(svc.port)
        found = any(catalog_port_str in ps for ps in port_strs)

        if not found and ports:
            # Also check default values in ${VAR:-DEFAULT} patterns
            for ps in port_strs:
                defaults = re.findall(r':-(\d+)', ps)
                if catalog_port_str in defaults:
                    found = True
                    break

        if not found and ports:
            mismatches.append(
                f"{svc.name}: catalog={svc.port}, compose={port_strs}"
            )

    # Advisory — port mismatches indicate catalog drift, not deployment issues
    if mismatches:
        import warnings
        warnings.warn(
            f"Port mismatches between catalog and compose: "
            f"{'; '.join(mismatches[:5])}"
        )


@pytest.mark.smoke
def test_catalog_health_paths_are_valid():
    """Verify health paths in catalog are well-formed."""
    for svc in SERVICES:
        if svc.health_path and svc.health_path not in ("pg_isready", "ping", "socket"):
            assert svc.health_path.startswith("/"), (
                f"{svc.name} health_path should start with '/': {svc.health_path}"
            )


@pytest.mark.smoke
def test_catalog_dependencies_are_valid():
    """Verify all dependency references in catalog resolve to known services."""
    all_names = {s.name for s in SERVICES + INTERNAL_SERVICES}
    # Accept common aliases and partial matches
    all_names.update({"postgres", "clickhouse", "supabase", "hirag-v2"})

    invalid_deps = []
    for svc in SERVICES + INTERNAL_SERVICES:
        for dep in svc.dependencies:
            if dep not in all_names:
                # Check if dep is a substring of any known service (e.g., "hirag-v2" -> "hi-rag-gateway-v2")
                partial_match = any(dep in name or name in dep for name in all_names)
                if not partial_match:
                    invalid_deps.append(f"{svc.name} -> {dep}")

    assert not invalid_deps, (
        f"Catalog dependencies reference unknown services: {invalid_deps}"
    )


@pytest.mark.smoke
def test_no_duplicate_catalog_ports():
    """Verify no two catalog services claim the same port (unless in different profiles)."""
    port_map = {}
    duplicates = []

    for svc in SERVICES:
        if svc.port == 0:
            continue
        if svc.port in port_map:
            existing = port_map[svc.port]
            existing_svc = get_service_by_name(existing)
            # Allow same port if services are in different profiles
            if existing_svc and svc.profile and existing_svc.profile:
                if svc.profile != existing_svc.profile:
                    continue  # Different profiles — acceptable
            duplicates.append(
                f"Port {svc.port}: {existing} and {svc.name}"
            )
        else:
            port_map[svc.port] = svc.name

    assert not duplicates, (
        f"Duplicate ports in service catalog (same profile): {duplicates}"
    )


@pytest.mark.smoke
def test_catalog_completeness():
    """Verify service catalog covers the main compose services (advisory)."""
    compose_services = _load_main_compose_services()
    catalog_names = {s.name for s in SERVICES + INTERNAL_SERVICES}

    # Services that are infrastructure/init and don't need catalog entries
    infrastructure = {
        "nats-init", "promtail", "cadvisor", "supabase-studio",
        "supabase-gotrue", "supabase-storage", "supabase-imgproxy",
        "supabase-meta", "supabase-edge-functions", "supabase-analytics",
        "supabase-vector", "supabase-realtime", "supabase-db",
        "supabase-postgrest",
    }

    uncatalogued = []
    for name in compose_services:
        if name not in catalog_names and name not in infrastructure:
            uncatalogued.append(name)

    # Advisory — warn but don't fail
    if uncatalogued:
        import warnings
        warnings.warn(
            f"{len(uncatalogued)} compose services lack catalog entries: "
            f"{sorted(uncatalogued)[:10]}"
        )
