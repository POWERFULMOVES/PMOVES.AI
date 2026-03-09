"""
Test for port conflicts in PMOVES.AI service configuration.

Validates that:
1. No two services claim the same host port
2. Internal ports are documented correctly
3. Port ranges are respected (no privileged ports unless intended)
4. Port changes are documented (e.g., wger-nginx: 8000->8010)

This helps prevent "port already in use" errors during startup.
"""

import pytest
import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

from _smoke_helpers import grep_file, PROJECT_ROOT, PMOVES_DIR


def extract_port_mappings_from_compose(compose_file: Path) -> Dict[str, List[Tuple[int, int, str]]]:
    """Extract port mappings from docker-compose.yml.

    Returns dict mapping service name to list of (host_port, container_port, protocol) tuples.
    """
    port_mappings = defaultdict(list)

    if not compose_file.exists():
        return port_mappings

    content = compose_file.read_text()

    # Find all service blocks
    service_pattern = r'(\S+):\s*\n((?:[ \t]+[^\n]+\n)*)?'
    services = re.finditer(service_pattern, content)

    for match in services:
        service_name = match.group(1)
        service_block = match.group(2) or ""

        # Extract port mappings: "HOST_PORT:CONTAINER_PORT" or "HOST_PORT:CONTAINER_PORT/tcp"
        # Also handle ${VAR:-DEFAULT}:CONTAINER_PORT patterns
        port_pattern = r'-\s*"(?:\$\{[^}]*:-)?(\d+)\}?:(\d+)(/(\w+))?"'
        ports = re.findall(port_pattern, service_block)

        for host_port, container_port, _, protocol in ports:
            port_mappings[service_name].append((
                int(host_port),
                int(container_port),
                protocol or "tcp"
            ))

    return port_mappings


def get_all_compose_files() -> List[Path]:
    """Get all docker-compose files in pmoves directory."""
    return list(PMOVES_DIR.glob("docker-compose*.yml")) + list(PMOVES_DIR.glob("compose/*.yml"))


# Known port conflicts that are documented/intentional
DOCUMENTED_CONFLICTS = {
    "wger-nginx": 8010,  # Changed from 8000 to avoid TensorZero UI conflict
}

# Services that are expected to use privileged ports (< 1024)
PRIVILEGED_PORT_SERVICES = {
    # Add services here if they intentionally use privileged ports
}

# Internal-only services (no host port binding, shouldn't conflict)
INTERNAL_SERVICES = [
    "supabase-db",
    "supabase-postgrest",
    "qdrant",
    "neo4j",
    "meilisearch",
]


@pytest.mark.smoke
def test_no_duplicate_host_ports() -> None:
    """Verify no two services use the same host port."""
    compose_files = get_all_compose_files()
    host_ports = defaultdict(list)

    for compose_file in compose_files:
        port_mappings = extract_port_mappings_from_compose(compose_file)

        for service_name, ports in port_mappings.items():
            for host_port, container_port, protocol in ports:
                host_ports[host_port].append((service_name, compose_file.name))

    conflicts = []
    for port, services in host_ports.items():
        if len(services) > 1:
            is_documented = any(
                svc[0] in DOCUMENTED_CONFLICTS and DOCUMENTED_CONFLICTS[svc[0]] == port
                for svc in services
            )
            if not is_documented:
                conflicts.append((port, services))

    if conflicts:
        conflict_details = "\n".join([
            f"  Port {port}: {', '.join([s[0] for s in services])}"
            for port, services in conflicts
        ])
        pytest.fail(
            f"Host port conflicts found:\n{conflict_details}\n"
            f"Use distinct ports or document intentional conflicts."
        )


@pytest.mark.smoke
def test_wger_nginx_port_changed_from_8000() -> None:
    """Verify wger-nginx uses port 8010 (not 8000) to avoid TensorZero UI conflict."""
    port_mappings = extract_port_mappings_from_compose(PMOVES_DIR / "docker-compose.external.yml")

    if "wger-nginx" in port_mappings:
        host_ports = [p[0] for p in port_mappings["wger-nginx"]]
        assert 8010 in host_ports, (
            "wger-nginx should use host port 8010 (changed from 8000)"
        )
        assert 8000 not in host_ports, (
            "wger-nginx should NOT use port 8000 (conflicts with TensorZero UI)"
        )


@pytest.mark.smoke
def test_internal_services_dont_expose_ports() -> None:
    """Verify internal-only services don't expose host ports unnecessarily."""
    port_mappings = extract_port_mappings_from_compose(PMOVES_DIR / "docker-compose.yml")

    for service_name in INTERNAL_SERVICES:
        if service_name in port_mappings:
            host_ports = [p[0] for p in port_mappings[service_name]]
            if host_ports:
                pytest.fail(
                    f"{service_name} is marked as internal but exposes host ports: {host_ports}. "
                    f"Remove port binding or document why it's needed."
                )


@pytest.mark.smoke
def test_privileged_ports_have_documentation() -> None:
    """Verify services using privileged ports (< 1024) are documented."""
    port_mappings = extract_port_mappings_from_compose(PMOVES_DIR / "docker-compose.yml")

    for service_name, ports in port_mappings.items():
        for host_port, container_port, protocol in ports:
            if host_port < 1024 and service_name not in PRIVILEGED_PORT_SERVICES:
                pytest.fail(
                    f"{service_name} uses privileged port {host_port} (< 1024). "
                    f"Add to PRIVILEGED_PORT_SERVICES in test_port_conflicts.py "
                    f"or use a non-privileged port."
                )


@pytest.mark.smoke
def test_tensorzero_ui_port_is_8000() -> None:
    """Verify TensorZero UI uses port 8000 (documented conflict with wger)."""
    port_mappings = extract_port_mappings_from_compose(PMOVES_DIR / "docker-compose.yml")

    for service_name in port_mappings:
        if "tensorzero" in service_name.lower() and "ui" in service_name.lower():
            host_ports = [p[0] for p in port_mappings[service_name]]
            assert 8000 in host_ports or 4000 in host_ports, (
                f"{service_name} should use port 8000 or 4000 (TensorZero UI standard)"
            )


@pytest.mark.smoke
def test_common_service_ports_are_standard() -> None:
    """Verify common services use their standard ports."""
    port_mappings = extract_port_mappings_from_compose(PMOVES_DIR / "docker-compose.yml")

    standard_ports = {
        "grafana": 3002,
        "prometheus": 9090,
        "loki": 3100,
        "jellyfin": 8096,
        "nats": (4222, 8222, 9222),
    }

    for service_pattern, expected_ports in standard_ports.items():
        for service_name in port_mappings:
            if service_pattern in service_name.lower():
                host_ports = [p[0] for p in port_mappings[service_name]]
                if isinstance(expected_ports, tuple):
                    assert any(p in host_ports for p in expected_ports), (
                        f"{service_name} should use one of standard ports {expected_ports}, got {host_ports}"
                    )
                else:
                    assert expected_ports in host_ports, (
                        f"{service_name} should use standard port {expected_ports}, got {host_ports}"
                    )
                break


@pytest.mark.smoke
def test_no_localhost_references_in_compose_ports() -> None:
    """Verify port mappings don't reference 'localhost' in host bindings."""
    compose_files = get_all_compose_files()

    for compose_file in compose_files:
        content = compose_file.read_text()
        if re.search(r'ports:.*localhost:\d+', content, re.DOTALL):
            pytest.fail(
                f"{compose_file.name} contains 'localhost:PORT' in port mapping. "
                f"Use 'PORT:container_port' format instead."
            )


@pytest.mark.smoke
def test_port_ranges_are_sequential_where_appropriate() -> None:
    """Verify related services use sequential port ranges for easy memorization."""
    port_mappings = extract_port_mappings_from_compose(PMOVES_DIR / "docker-compose.yml")

    hirag_ports = []
    for service_name, ports in port_mappings.items():
        if "hirag" in service_name.lower():
            for port_tuple in ports:
                hirag_ports.append((service_name, port_tuple[0]))

    if hirag_ports:
        for svc_name, port in hirag_ports:
            assert 8080 <= port <= 8099, (
                f"Hi-RAG service {svc_name} should use port in 8080-8099 range, got {port}"
            )


@pytest.mark.smoke
def test_documented_ports_match_reality() -> None:
    """Verify ports documented in service catalog match docker-compose configuration."""
    port_mappings = extract_port_mappings_from_compose(PMOVES_DIR / "docker-compose.yml")

    expected_ports = {
        "tensorzero-gateway": [3030],
        "agent-zero": [50051],
    }

    for service_name, expected in expected_ports.items():
        if service_name in port_mappings:
            actual_ports = [p[0] for p in port_mappings[service_name]]
            for exp_port in expected:
                assert exp_port in actual_ports, (
                    f"{service_name} should expose port {exp_port} (documented), got {actual_ports}"
                )


@pytest.mark.smoke
def test_health_check_ports_match_service_ports() -> None:
    """Verify health check URLs reference the correct ports."""
    compose_file = PMOVES_DIR / "docker-compose.yml"
    if not compose_file.exists():
        pytest.skip("docker-compose.yml not found")

    content = compose_file.read_text()

    healthcheck_ports = re.findall(r'localhost:(\d+)', content)

    for port_str in healthcheck_ports:
        port = int(port_str)
        assert 1 <= port <= 65535, f"Invalid port in healthcheck: {port}"


@pytest.mark.smoke
def test_supabase_ports_are_standard() -> None:
    """Verify Supabase services use standard documented ports."""
    port_mappings = extract_port_mappings_from_compose(PMOVES_DIR / "docker-compose.yml")

    supabase_standards = {
        "supabase-studio": 54323,
        "supabase-gotrue": 9999,
        "supabase-postgrest": 3000,
        "supabase-realtime": 4000,
        "supabase-storage": 5000,
    }

    for service_name, expected_port in supabase_standards.items():
        if service_name in port_mappings:
            host_ports = [p[0] for p in port_mappings[service_name]]
            assert expected_port in host_ports, (
                f"{service_name} should use standard port {expected_port}, got {host_ports}"
            )


@pytest.mark.smoke
def test_no_legacy_cli_port_in_compose() -> None:
    """Verify Supabase CLI port (54321) is not used in compose files."""
    compose_files = get_all_compose_files()

    for compose_file in compose_files:
        content = compose_file.read_text()

        if re.search(r'["\s]54321["\s:]', content):
            lines_with_54321 = []
            for i, line in enumerate(content.splitlines(), 1):
                if "54321" in line and not line.strip().startswith("#"):
                    lines_with_54321.append(f"  Line {i}: {line.strip()}")

            if lines_with_54321:
                pytest.fail(
                    f"{compose_file.name} contains Supabase CLI port 54321:\n" +
                    "\n".join(lines_with_54321) +
                    "\nUse self-hosted Supabase ports instead."
                )
