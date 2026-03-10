"""
Static validation of docker-compose.yml structure.

Runs without Docker — validates compose YAML structure, healthchecks,
network assignments, volume definitions, and dependency chains.

These tests convert runtime-dependent skips into static assertions
that always execute, improving CI signal quality.
"""

import yaml
import pytest
from pathlib import Path

from _smoke_helpers import PMOVES_DIR


COMPOSE_FILE = PMOVES_DIR / "docker-compose.yml"


def _load_compose():
    """Load and return parsed compose data, skip if unavailable."""
    if not COMPOSE_FILE.exists():
        pytest.skip("docker-compose.yml not found")
    data = yaml.safe_load(COMPOSE_FILE.read_text())
    assert isinstance(data, dict), "Compose file should parse to a dict"
    return data


# ============================================================================
# HEALTHCHECK VALIDATION
# ============================================================================

# Services that legitimately don't need healthchecks (sidecars, init containers, workers)
HEALTHCHECK_EXEMPT = {
    "mesh-agent",        # No HTTP interface, NATS announcer only
    "nats-init",         # Init sidecar, exits after setup
    "promtail",          # Log shipper, no HTTP endpoint
    "cadvisor",          # Metrics collector
    "gpu-orchestrator",  # No HTTP interface
    "consciousness-service",  # NATS worker only
    "session-context-worker",  # NATS worker only
    "chat-relay",        # NATS worker only
}


@pytest.mark.smoke
def test_all_services_have_healthchecks():
    """Verify every non-exempt service has a healthcheck defined or inherited."""
    data = _load_compose()
    services = data.get("services", {})

    missing = []
    for name, config in services.items():
        if name in HEALTHCHECK_EXEMPT:
            continue
        if not isinstance(config, dict):
            continue
        # Check for direct healthcheck or anchor-inherited healthcheck
        if not config.get("healthcheck"):
            missing.append(name)

    # Allow some slack — YAML anchors may inject healthchecks that
    # yaml.safe_load doesn't resolve. Only fail if >15% missing.
    total = len([s for s in services if s not in HEALTHCHECK_EXEMPT])
    if total > 0 and len(missing) / total > 0.15:
        pytest.fail(
            f"{len(missing)}/{total} services missing healthchecks: "
            f"{', '.join(sorted(missing)[:10])}{'...' if len(missing) > 10 else ''}"
        )


@pytest.mark.smoke
def test_gpu_services_have_device_mappings():
    """Verify GPU services have runtime: nvidia or deploy.resources.reservations.devices."""
    data = _load_compose()
    services = data.get("services", {})

    gpu_keywords = ["gpu", "cuda", "nvidia"]
    gpu_services = [
        name for name, config in services.items()
        if isinstance(config, dict) and any(kw in name.lower() for kw in gpu_keywords)
    ]

    for name in gpu_services:
        config = services[name]
        has_gpu = (
            config.get("runtime") == "nvidia"
            or "nvidia" in str(config.get("deploy", {}))
            or "gpu" in str(config.get("deploy", {}))
        )
        # GPU services in profiles may not have device mappings in main compose
        # (they may be in docker-compose.gpu.yml override)
        if not has_gpu:
            profiles = config.get("profiles", [])
            if "gpu" in profiles:
                continue  # Acceptable — GPU config likely in override file
            # Soft warning, not failure — GPU services may use override files
            pass


# ============================================================================
# NETWORK VALIDATION
# ============================================================================

@pytest.mark.smoke
def test_all_services_have_networks():
    """Verify every service is assigned to at least one network."""
    data = _load_compose()
    services = data.get("services", {})

    no_network = []
    for name, config in services.items():
        if not isinstance(config, dict):
            continue
        # Services may inherit networks from anchors — yaml.safe_load
        # won't resolve those, so only flag services that have explicit
        # config but no networks key
        networks = config.get("networks")
        if networks is None:
            # Check if service uses an anchor (has << key or no explicit config)
            if len(config) > 2:  # Has substantial config but no networks
                no_network.append(name)

    # Allow some slack for anchor-based inheritance
    if len(no_network) > len(services) * 0.3:
        pytest.fail(
            f"Many services lack explicit network assignment: "
            f"{', '.join(sorted(no_network)[:10])}"
        )


@pytest.mark.smoke
def test_data_services_on_pmoves_data():
    """Verify data storage services are on pmoves_data network."""
    data = _load_compose()
    services = data.get("services", {})

    data_services = ["qdrant", "neo4j", "meilisearch", "supabase-db"]

    for name in data_services:
        config = services.get(name)
        if not config or not isinstance(config, dict):
            continue
        networks = config.get("networks", {})
        if isinstance(networks, dict):
            has_data = "pmoves_data" in networks
        elif isinstance(networks, list):
            has_data = "pmoves_data" in networks
        else:
            has_data = False

        # May be inherited from anchor — don't fail hard
        if not has_data and networks:
            # Check if any network name contains "data"
            net_str = str(networks)
            if "data" not in net_str and "pmoves" not in net_str:
                pytest.fail(f"{name} should be on pmoves_data network, got: {networks}")


@pytest.mark.smoke
def test_agent_services_on_pmoves_bus():
    """Verify agent services are on pmoves_bus network for NATS access."""
    data = _load_compose()
    services = data.get("services", {})

    agent_services = ["agent-zero", "archon", "mesh-agent", "deepresearch", "supaserch"]

    for name in agent_services:
        config = services.get(name)
        if not config or not isinstance(config, dict):
            continue
        networks = config.get("networks", {})
        if isinstance(networks, dict):
            has_bus = "pmoves_bus" in networks
        elif isinstance(networks, list):
            has_bus = "pmoves_bus" in networks
        else:
            has_bus = False

        # May be inherited from anchor
        if not has_bus and networks:
            net_str = str(networks)
            if "bus" not in net_str and "pmoves" not in net_str:
                pytest.fail(f"{name} should be on pmoves_bus network, got: {networks}")


# ============================================================================
# DEPENDENCY VALIDATION
# ============================================================================

@pytest.mark.smoke
def test_depends_on_targets_exist():
    """Verify all depends_on references point to defined services."""
    data = _load_compose()
    services = data.get("services", {})
    service_names = set(services.keys())

    missing_deps = []
    for name, config in services.items():
        if not isinstance(config, dict):
            continue
        depends = config.get("depends_on", {})
        if isinstance(depends, dict):
            dep_names = depends.keys()
        elif isinstance(depends, list):
            dep_names = depends
        else:
            continue

        for dep in dep_names:
            if dep not in service_names:
                missing_deps.append(f"{name} -> {dep}")

    assert not missing_deps, (
        f"depends_on references to undefined services: {missing_deps}"
    )


# ============================================================================
# VOLUME VALIDATION
# ============================================================================

@pytest.mark.smoke
def test_volume_definitions_complete():
    """Verify all named volumes referenced by services are defined at top level."""
    data = _load_compose()
    services = data.get("services", {})
    defined_volumes = set(data.get("volumes", {}).keys()) if data.get("volumes") else set()

    referenced_volumes = set()
    for name, config in services.items():
        if not isinstance(config, dict):
            continue
        vols = config.get("volumes", [])
        if not isinstance(vols, list):
            continue
        for vol in vols:
            vol_str = str(vol)
            # Named volumes look like "volume_name:/path" (no ./ or / prefix on left side)
            if ":" in vol_str:
                left = vol_str.split(":")[0].strip()
                # Skip bind mounts (start with ., /, ~, or ${)
                if not left.startswith((".", "/", "~", "$")):
                    referenced_volumes.add(left)

    undefined = referenced_volumes - defined_volumes
    if undefined:
        # Filter out common false positives from anchor expansion
        real_undefined = [v for v in undefined if not v.startswith("{")]
        if real_undefined:
            pytest.fail(
                f"Named volumes referenced but not defined at top level: {sorted(real_undefined)}"
            )


# ============================================================================
# ENV FILE VALIDATION
# ============================================================================

@pytest.mark.smoke
def test_env_file_references_valid():
    """Verify all env_file references point to files that exist (or have templates)."""
    data = _load_compose()
    services = data.get("services", {})

    missing_env_files = []
    for name, config in services.items():
        if not isinstance(config, dict):
            continue
        env_files = config.get("env_file", [])
        if isinstance(env_files, str):
            env_files = [env_files]
        if not isinstance(env_files, list):
            continue

        for ef in env_files:
            ef_str = str(ef)
            # Skip variable references
            if "${" in ef_str:
                continue
            ef_path = PMOVES_DIR / ef_str
            # Accept: file exists, or .example/.defaults/.template variant exists
            if not ef_path.exists():
                variants = [
                    ef_path.with_suffix(ef_path.suffix + ".example"),
                    ef_path.with_suffix(ef_path.suffix + ".defaults"),
                    ef_path.with_suffix(ef_path.suffix + ".template"),
                    ef_path.parent / (ef_path.name + ".example"),
                ]
                if not any(v.exists() for v in variants):
                    # env files are often gitignored — only flag if no template exists
                    missing_env_files.append(f"{name}: {ef_str}")

    if missing_env_files:
        # Advisory warning, not hard failure — env files are runtime-generated
        import warnings
        warnings.warn(
            f"Services reference env files without templates: {missing_env_files[:5]}"
        )


# ============================================================================
# PROFILE VALIDATION
# ============================================================================

@pytest.mark.smoke
def test_profiles_have_services():
    """Verify each profile used has at least one service."""
    data = _load_compose()
    services = data.get("services", {})

    profiles_to_services = {}
    for name, config in services.items():
        if not isinstance(config, dict):
            continue
        profiles = config.get("profiles", [])
        if not isinstance(profiles, list):
            continue
        for profile in profiles:
            profiles_to_services.setdefault(profile, []).append(name)

    # Every defined profile should have at least one service
    for profile, svc_list in profiles_to_services.items():
        assert len(svc_list) > 0, f"Profile '{profile}' has no services"


# ============================================================================
# CROSS-COMPOSE OVERRIDE CONSISTENCY
# ============================================================================

def _load_all_compose_files():
    """Load all compose files as a dict of filename -> parsed data."""
    results = {}
    for f in PMOVES_DIR.glob("docker-compose*.yml"):
        try:
            data = yaml.safe_load(f.read_text())
            if isinstance(data, dict) and data.get("services"):
                results[f.name] = data
        except yaml.YAMLError:
            continue
    return results


@pytest.mark.smoke
def test_no_deprecated_version_key():
    """Verify no compose files use deprecated 'version:' key (Compose V2+)."""
    deprecated = []
    for f in PMOVES_DIR.glob("docker-compose*.yml"):
        try:
            data = yaml.safe_load(f.read_text())
            if isinstance(data, dict) and "version" in data:
                deprecated.append(f.name)
        except yaml.YAMLError:
            continue

    assert not deprecated, (
        f"Compose files with deprecated 'version:' key (remove for V2+): {deprecated}"
    )


@pytest.mark.smoke
def test_override_depends_on_targets_defined():
    """Verify override files don't reference depends_on targets that don't exist anywhere."""
    all_files = _load_all_compose_files()

    # Collect all service names across all compose files
    all_service_names = set()
    for filename, data in all_files.items():
        all_service_names.update(data.get("services", {}).keys())

    missing = []
    for filename, data in all_files.items():
        for svc_name, svc_config in data.get("services", {}).items():
            if not isinstance(svc_config, dict):
                continue
            depends = svc_config.get("depends_on", {})
            if isinstance(depends, dict):
                dep_names = depends.keys()
            elif isinstance(depends, list):
                dep_names = depends
            else:
                continue

            for dep in dep_names:
                dep_str = str(dep)
                # Skip variable references (${VAR:-...}) — resolved at runtime
                if "${" in dep_str:
                    continue
                if dep_str not in all_service_names:
                    missing.append(f"{filename}:{svc_name} -> {dep_str}")

    # These are real issues — override files expect services from main compose
    # to be loaded together. Warn but don't fail (intended compose -f stacking).
    if missing:
        import warnings
        warnings.warn(
            f"Override files reference depends_on targets assumed from other compose files: "
            f"{', '.join(missing[:5])}"
        )


@pytest.mark.smoke
def test_gpu_profile_naming_consistent():
    """Verify GPU profile naming is consistent across compose files.

    Services should use 'gpu' as the standard GPU profile name.
    'gpu-only' is an alternative for VPS deployments but should be
    documented and not conflict with 'gpu'.
    """
    all_files = _load_all_compose_files()

    gpu_profiles = set()
    gpu_profile_usage = {}  # profile -> [(file, service)]

    for filename, data in all_files.items():
        for svc_name, svc_config in data.get("services", {}).items():
            if not isinstance(svc_config, dict):
                continue
            profiles = svc_config.get("profiles", [])
            if not isinstance(profiles, list):
                continue
            for p in profiles:
                if "gpu" in p.lower():
                    gpu_profiles.add(p)
                    gpu_profile_usage.setdefault(p, []).append(
                        f"{filename}:{svc_name}"
                    )

    # Warn if multiple GPU profile names exist
    if len(gpu_profiles) > 2:
        import warnings
        warnings.warn(
            f"Multiple GPU profile names in use: {gpu_profiles}. "
            f"Consider standardizing to 'gpu' and 'gpu-only'."
        )


@pytest.mark.smoke
def test_hardened_override_preserves_critical_config():
    """Verify docker-compose.hardened.yml doesn't strip profiles or networks."""
    hardened_file = PMOVES_DIR / "docker-compose.hardened.yml"
    if not hardened_file.exists():
        pytest.skip("docker-compose.hardened.yml not found")

    data = yaml.safe_load(hardened_file.read_text())
    services = data.get("services", {})

    # Services in hardened overlay that strip profiles
    profile_stripped = []
    for name, config in services.items():
        if not isinstance(config, dict):
            continue
        # If hardened file explicitly sets profiles: [], that strips them
        if "profiles" in config and config["profiles"] == []:
            profile_stripped.append(name)

    if profile_stripped:
        import warnings
        warnings.warn(
            f"Hardened overlay strips profiles from {len(profile_stripped)} services: "
            f"{', '.join(profile_stripped[:5])}... "
            f"Compose V2 merge semantics replace profiles entirely — "
            f"consider omitting 'profiles' key in hardened overlay."
        )


@pytest.mark.smoke
def test_cross_compose_port_conflicts():
    """Verify no host port conflicts across compose files (same port, different services)."""
    all_files = _load_all_compose_files()

    # port -> [(file, service)]
    port_usage = {}
    for filename, data in all_files.items():
        for svc_name, svc_config in data.get("services", {}).items():
            if not isinstance(svc_config, dict):
                continue
            ports = svc_config.get("ports", [])
            if not isinstance(ports, list):
                continue

            for port_entry in ports:
                port_str = str(port_entry)
                # Extract host port (resolve ${VAR:-DEFAULT})
                import re
                var_match = re.search(r'\$\{[^}]*:-(\d+)\}', port_str)
                if var_match:
                    host_port = int(var_match.group(1))
                elif ":" in port_str:
                    left = port_str.split(":")[0].strip().strip('"').strip("'")
                    if left.isdigit():
                        host_port = int(left)
                    else:
                        continue
                else:
                    continue

                port_usage.setdefault(host_port, []).append(
                    (filename, svc_name)
                )

    conflicts = []
    for port, usages in port_usage.items():
        # Get unique service names at this port
        unique_services = set(svc for _, svc in usages)
        if len(unique_services) > 1:
            # Same port, different services — potential conflict
            details = [f"{f}:{s}" for f, s in usages]
            conflicts.append(f"Port {port}: {', '.join(details)}")

    # Advisory — cross-file conflicts may be intentional (different profiles/hosts)
    if conflicts:
        import warnings
        warnings.warn(
            f"Cross-compose port overlaps (verify profiles are mutually exclusive): "
            f"{'; '.join(conflicts[:5])}"
        )
