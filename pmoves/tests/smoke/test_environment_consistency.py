"""
Test environment variable consistency across PMOVES.AI configuration files.

Validates that environment variables are consistently defined across:
- env.shared (base configuration)
- env.tier-* files (tier-specific configuration)
- docker-compose.yml (service environment)

This test helps prevent configuration drift and ensures services
can access the variables they expect.
"""

import os
import pytest
import subprocess
import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Set


PROJECT_ROOT = Path(__file__).resolve().parents[3]
PMOVES_DIR = PROJECT_ROOT / "pmoves"


def extract_env_vars_from_file(file_path: Path) -> Dict[str, str]:
    """Extract environment variable definitions from a file.

    Returns dict mapping variable name to its value (or placeholder if unset).
    """
    env_vars = {}
    if not file_path.exists():
        return env_vars

    try:
        content = file_path.read_text()
        for line in content.splitlines():
            line = line.strip()
            # Skip comments and empty lines
            if not line or line.startswith("#"):
                continue

            # Match: VAR_NAME=value or VAR_NAME=${DEFAULT}
            match = re.match(r"^([A-Z_][A-Z0-9_]*)=(.*)$", line)
            if match:
                var_name = match.group(1)
                var_value = match.group(2)
                env_vars[var_name] = var_value
    except Exception as e:
        pytest.fail(f"Failed to read {file_path}: {e}")

    return env_vars


def extract_env_vars_from_compose(service_name: str) -> Dict[str, str]:
    """Extract environment variables for a service from docker-compose.yml."""
    env_vars = {}
    compose_file = PMOVES_DIR / "docker-compose.yml"

    if not compose_file.exists():
        return env_vars

    result = subprocess.run(
        ["grep", "-A", "50", f"{service_name}:", str(compose_file)],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        return env_vars

    in_service = False
    in_environment = False

    for line in result.stdout.splitlines():
        line = line.strip()

        # Detect service block
        if line.startswith(f"{service_name}:"):
            in_service = True
            continue
        elif in_service and line and not line.startswith("-") and ":" in line:
            # New service section (not an environment line)
            if not line.startswith("-"):
                break

        # Extract environment variables
        if in_service and line.startswith("environment:"):
            in_environment = True
            continue
        elif in_environment and line.startswith("- "):
            # - VAR_NAME=value or - VAR_NAME=${DEFAULT}
            match = re.match(r'-\s*([A-Z_][A-Z0-9_]*)=(.*)$', line)
            if match:
                var_name = match.group(1)
                var_value = match.group(2)
                env_vars[var_name] = var_value
        elif in_environment and line and not line.startswith("-"):
            # End of environment section
            break

    return env_vars


def get_all_env_files() -> List[Path]:
    """Get all environment files in pmoves directory."""
    return [
        PMOVES_DIR / "env.shared",
        PMOVES_DIR / "env.tier-api",
        PMOVES_DIR / "env.tier-media",
        PMOVES_DIR / "env.tier-worker",
        PMOVES_DIR / "env.tier-supabase",
    ]


@pytest.mark.smoke
def test_env_shared_exists() -> None:
    """Verify env.shared exists and has required variables."""
    env_shared = PMOVES_DIR / "env.shared"
    assert env_shared.exists(), "env.shared should exist"

    env_vars = extract_env_vars_from_file(env_shared)

    # Check for critical variables
    critical_vars = ["NATS_URL", "POSTGRES_USER", "POSTGRES_PASSWORD"]
    for var in critical_vars:
        # Variable should be defined (value may be placeholder)
        assert var in env_vars, f"{var} should be defined in env.shared"


@pytest.mark.smoke
def test_no_duplicate_jwt_secrets() -> None:
    """Verify JWT secret is not duplicated across env files."""
    all_files = get_all_env_files()
    jwt_locations = []

    for env_file in all_files:
        if not env_file.exists():
            continue

        env_vars = extract_env_vars_from_file(env_file)
        if "SUPABASE_JWT_SECRET" in env_vars:
            value = env_vars["SUPABASE_JWT_SECRET"]
            # Check if it's an actual value (not a reference or placeholder)
            if not value.startswith("${") and not value.startswith("your_") and not value.startswith("PLACEHOLDER"):
                jwt_locations.append((env_file.name, value[:20] + "..."))

    # JWT secret should only be in env.tier-supabase
    assert len(jwt_locations) <= 1, (
        f"SUPABASE_JWT_SECRET should only be in env.tier-supabase. "
        f"Found in: {jwt_locations}"
    )


@pytest.mark.smoke
def test_supabase_url_consistency() -> None:
    """Verify Supabase URL references are consistent."""
    env_shared = PMOVES_DIR / "env.shared"
    if not env_shared.exists():
        pytest.skip("env.shared not found")

    env_vars = extract_env_vars_from_file(env_shared)

    # Check that SUPA_REST_URL points to self-hosted, not CLI
    if "SUPA_REST_URL" in env_vars:
        url = env_vars["SUPA_REST_URL"]
        # Should not reference CLI port 54321
        assert "54321" not in url, (
            f"SUPA_REST_URL should not reference CLI port 54321, got: {url}"
        )
        # Should reference supabase-postgrest or postgrest container
        assert "supabase-postgrest" in url or "postgrest:" in url, (
            f"SUPA_REST_URL should reference self-hosted postgrest, got: {url}"
        )


@pytest.mark.smoke
def test_nats_url_consistency() -> None:
    """Verify NATS_URL is consistently defined across files."""
    all_files = get_all_env_files()
    nats_urls = []

    for env_file in all_files:
        if not env_file.exists():
            continue

        env_vars = extract_env_vars_from_file(env_file)
        if "NATS_URL" in env_vars:
            nats_urls.append((env_file.name, env_vars["NATS_URL"]))

    # All NATS_URL references should point to the same host
    if len(nats_urls) > 1:
        # Extract host from first URL as reference
        first_host = nats_urls[0][1].split("@")[-1].split("/")[0] if "@" in nats_urls[0][1] else nats_urls[0][1]

        for file_name, url in nats_urls[1:]:
            this_host = url.split("@")[-1].split("/")[0] if "@" in url else url
            assert this_host == first_host or "${" in this_host, (
                f"NATS_URL host mismatch: {file_name} has {this_host}, expected {first_host}"
            )


@pytest.mark.smoke
def test_database_url_references_correct_host() -> None:
    """Verify database URLs reference correct Supabase host."""
    env_shared = PMOVES_DIR / "env.shared"
    if not env_shared.exists():
        pytest.skip("env.shared not found")

    env_vars = extract_env_vars_from_file(env_shared)

    # Check CHANNEL_MONITOR_DATABASE_URL
    if "CHANNEL_MONITOR_DATABASE_URL" in env_vars:
        url = env_vars["CHANNEL_MONITOR_DATABASE_URL"]
        # Should reference supabase-db, not host.docker.internal
        assert "supabase-db" in url or "postgres:" in url, (
            f"CHANNEL_MONITOR_DATABASE_URL should reference supabase-db container, got: {url}"
        )


@pytest.mark.smoke
def test_compose_services_use_env_vars() -> None:
    """Verify docker-compose services reference environment variables correctly."""
    compose_file = PMOVES_DIR / "docker-compose.yml"
    if not compose_file.exists():
        pytest.skip("docker-compose.yml not found")

    # Check that services use ${VAR} for sensitive values, not hardcoded
    sensitive_patterns = [
        "password=",
        "secret=",
        "api_key=",
        "SUPABASE_SERVICE_ROLE_KEY=",
    ]

    for pattern in sensitive_patterns:
        result = subprocess.run(
            ["grep", "-n", pattern, str(compose_file)],
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:
            for line in result.stdout.splitlines():
                # Skip if it's a comment or environment variable reference
                if not line.strip().startswith("#") and "${" not in line:
                    # Allow specific patterns that are OK
                    if "DB_PASSWORD=" not in line and "JWT_SECRET=" not in line:
                        pytest.fail(
                            f"Possible hardcoded value in docker-compose.yml: {line}"
                        )


@pytest.mark.smoke
def test_env_files_have_no_export_keywords() -> None:
    """Verify environment files don't have 'export' keywords (Docker Compose doesn't parse them)."""
    all_files = get_all_env_files()

    for env_file in all_files:
        if not env_file.exists():
            continue

        result = subprocess.run(
            ["grep", "^export", str(env_file)],
            capture_output=True,
        )

        if result.returncode == 0:
            pytest.fail(
                f"{env_file.name} contains 'export' keyword. "
                f"Docker Compose doesn't parse 'export VAR=value' syntax."
            )


@pytest.mark.smoke
def test_tier_files_have_header_comment() -> None:
    """Verify tier environment files have descriptive headers."""
    tier_files = [
        PMOVES_DIR / "env.tier-api",
        PMOVES_DIR / "env.tier-media",
        PMOVES_DIR / "env.tier-worker",
        PMOVES_DIR / "env.tier-supabase",
    ]

    for env_file in tier_files:
        if not env_file.exists():
            continue

        # Check first few lines for header comment
        content = env_file.read_text()
        first_lines = "\n".join(content.splitlines()[:5])

        # Should have some comment explaining the file's purpose
        assert "#" in first_lines, (
            f"{env_file.name} should have a header comment explaining its purpose"
        )


@pytest.mark.smoke
def test_postgres_password_alignment() -> None:
    """Verify POSTGRES_PASSWORD is consistent across references."""
    env_files = [
        PMOVES_DIR / "env.shared",
        PMOVES_DIR / "env.tier-supabase",
    ]

    passwords = {}
    for env_file in env_files:
        if not env_file.exists():
            continue

        env_vars = extract_env_vars_from_file(env_file)
        for var_name in ["POSTGRES_PASSWORD", "SUPABASE_DB_PASSWORD"]:
            if var_name in env_vars:
                value = env_vars[var_name]
                # Skip placeholder values for this check
                if not any(
                    placeholder in value
                    for placeholder in ["your_", "PLACEHOLDER", "changeme", "$"]
                ):
                    passwords[f"{env_file.name}:{var_name}"] = value

    # All non-placeholder passwords should be the same (or references to the same var)
    unique_values = set(passwords.values())
    if len(unique_values) > 1:
        # Check if they're all references to environment variables
        for val in unique_values:
            if not val.startswith("${"):
                pytest.fail(
                    f"Inconsistent POSTGRES_PASSWORD values: {passwords}"
                )


@pytest.mark.smoke
def test_no_trailing_whitespace_in_env_files() -> None:
    """Verify environment files don't have trailing whitespace (causes parsing issues)."""
    all_files = get_all_env_files()

    for env_file in all_files:
        if not env_file.exists():
            continue

        result = subprocess.run(
            ["grep", "-n", " $" , str(env_file)],
            capture_output=True,
        )

        if result.returncode == 0:
            lines = result.stdout.strip().split("\n")
            pytest.fail(
                f"{env_file.name} has trailing whitespace on {len(lines)} line(s): {result.stdout[:100]}"
            )


@pytest.mark.smoke
def test_environment_variable_naming_convention() -> None:
    """Verify environment variables follow naming conventions."""
    all_files = get_all_env_files()

    for env_file in all_files:
        if not env_file.exists():
            continue

        env_vars = extract_env_vars_from_file(env_file)

        for var_name in env_vars:
            # Should be uppercase with underscores
            assert var_name.isupper(), (
                f"{env_file.name}: Variable '{var_name}' should be uppercase"
            )
            # Should not start with a number
            assert not var_name[0].isdigit(), (
                f"{env_file.name}: Variable '{var_name}' should not start with a digit"
            )
            # Should only contain alphanumeric and underscore
            assert var_name.replace("_", "").isalnum(), (
                f"{env_file.name}: Variable '{var_name}' should only contain [A-Z0-9_]"
            )


@pytest.mark.smoke
def test_critical_services_have_required_env_vars() -> None:
    """Verify critical services have their required environment variables defined."""
    # Check hirag-v2 service
    hirag_vars = extract_env_vars_from_compose("hirag-v2")

    if hirag_vars:
        required_vars = [
            "QDRANT_URL",
            "SUPABASE_REALTIME_URL",
        ]

        for var in required_vars:
            # Variable should be defined (as literal or env reference)
            found = False
            for env_var in hirag_vars:
                if var in env_var or var in hirag_vars:
                    found = True
                    break

            assert found, (
                f"hirag-v2 service should have {var} defined in docker-compose.yml"
            )
    else:
        pytest.skip("hirag-v2 service not found in docker-compose.yml")
