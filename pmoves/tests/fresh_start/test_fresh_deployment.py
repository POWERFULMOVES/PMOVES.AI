#!/usr/bin/env python3
"""Fresh Start Tests: Fresh Deployment Smoke Tests.

Tests for verifying a fresh deployment works correctly.
These tests may be destructive and should be run in a test environment.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import time
import uuid
from pathlib import Path

import pytest

# Add repo root to path
# Find the actual repo root by looking for .git directory
current = Path(__file__).resolve()
REPO_ROOT = current
while REPO_ROOT.parent != REPO_ROOT and not (REPO_ROOT / ".git").exists():
    REPO_ROOT = REPO_ROOT.parent

PMOVES_DIR = REPO_ROOT / "pmoves"
sys.path.insert(0, str(REPO_ROOT))


# ---------------------------------------------------------------------------
# Destructive-fixture isolation (incident 2026-09-26)
#
# `fresh_deployment` used to run `docker compose down` (setup) and
# `docker compose up -d` (teardown) with cwd=PMOVES_DIR and no `-p`. Those calls
# load pmoves/docker-compose.yml, whose top-level `name: pmoves` sets the
# project name -- the LIVE stack's project -- regardless of the directory the
# call is made from. A full-suite run from worktrees therefore removed all 19
# default-profile containers of the running stack, and the teardown `up -d`
# failed without env files.
#
# The fixture now makes NO compose calls at all. Nothing in this module needs a
# fresh stack: the health tests probe whatever is already listening. A
# throwaway-project `down` would be pure risk -- the fixture creates nothing to
# clean up, and docker-compose.yml declares fixed-name networks (pmoves_data,
# pmoves_public, pmoves_api, pmoves_app, pmoves_bus, pmoves_monitoring, ...)
# that older compose versions remove BY NAME. It never runs `up` either: those
# fixed-name networks and the published host ports are shared with the live
# stack whatever `-p` says.
#
# What remains is fail-closed:
#   * skip unless PMOVES_DESTRUCTIVE_TESTS=1, checked BEFORE touching Docker
#     at all (not even `docker info`);
#   * refuse if COMPOSE_PROJECT_NAME in the environment names the live project;
#   * yield a throwaway `pmoves-test-<8 hex>` project name, and `compose_argv()`
#     for any future caller: it puts `-p <that name>` in argv and refuses the
#     live name and `down -v/--volumes`. Note `-p` overrides `name:`; a call
#     without it does not.
# ---------------------------------------------------------------------------
DESTRUCTIVE_OPT_IN_ENV = "PMOVES_DESTRUCTIVE_TESTS"
LIVE_PROJECT_NAME = "pmoves"
TEST_PROJECT_PREFIX = "pmoves-test-"
TEST_PROJECT_RE = re.compile(r"^pmoves-test-[0-9a-f]{8}$")


def throwaway_project_name() -> str:
    """Return a fresh `pmoves-test-<8 hex>` compose project name."""
    return f"{TEST_PROJECT_PREFIX}{uuid.uuid4().hex[:8]}"


def compose_argv(project: str, *args: str) -> list[str]:
    """Build a `docker compose` argv pinned to a throwaway project.

    Raises instead of returning an argv that could address the live project
    (`-p` is required because docker-compose.yml's `name: pmoves` wins
    otherwise) or delete volumes.
    """
    if project.strip().lower() == LIVE_PROJECT_NAME or not TEST_PROJECT_RE.match(project):
        raise RuntimeError(
            f"refusing docker compose with project {project!r}: only "
            f"{TEST_PROJECT_RE.pattern} is allowed from tests"
        )
    if "down" in args and any(a in ("-v", "--volumes") or a.startswith("--volumes=") for a in args):
        raise RuntimeError("refusing `docker compose down -v/--volumes` from tests")
    return ["docker", "compose", "-p", project, *args]


def destructive_refusal(env: dict[str, str] | None = None) -> str | None:
    """Return why the destructive fixture must not run, or None if it may."""
    env = os.environ if env is None else env
    if env.get(DESTRUCTIVE_OPT_IN_ENV) != "1":
        return (
            f"fresh_deployment is destructive and opt-in only: set "
            f"{DESTRUCTIVE_OPT_IN_ENV}=1 to run it (it will use a throwaway "
            f"'{TEST_PROJECT_PREFIX}<hex>' compose project, never '{LIVE_PROJECT_NAME}')"
        )
    if env.get("COMPOSE_PROJECT_NAME", "").strip().lower() == LIVE_PROJECT_NAME:
        return (
            f"COMPOSE_PROJECT_NAME={LIVE_PROJECT_NAME!r} is the live stack's project; "
            "refusing to run the destructive fixture with it in the environment"
        )
    return None


def _docker_is_available() -> bool:
    try:
        result = subprocess.run(["docker", "info"], capture_output=True, timeout=10)
    except Exception:
        return False
    return result.returncode == 0


@pytest.fixture(scope="module")
def docker_available():
    """Check if Docker is available (read-only `docker info`)."""
    if not _docker_is_available():
        pytest.skip("Docker is not running or not available")
    return True


@pytest.fixture(scope="module")
def fresh_deployment():
    """Opt-in gate for the service-health tests; makes no compose calls.

    Deliberately does NOT depend on the ``docker_available`` fixture, because
    that would run ``docker info`` before the opt-in gate. The gate comes first;
    the only Docker contact after it is the read-only ``docker info``.

    Yields a throwaway project name for any test that needs one (build its
    argv with ``compose_argv``).
    """
    reason = destructive_refusal()
    if reason:
        pytest.skip(reason)
    if not _docker_is_available():
        pytest.skip("Docker is not running or not available")
    yield throwaway_project_name()


class TestDatabaseMigrations:
    """Test database migrations are applied correctly."""

    def test_supabase_migrations_exist(self):
        """Supabase migration files should exist."""
        migrations_dir = PMOVES_DIR / "supabase" / "migrations"
        assert migrations_dir.exists(), "Supabase migrations directory not found"

        migration_files = list(migrations_dir.glob("*.sql"))
        assert len(migration_files) > 0, "No migration files found"

    def test_supabase_migrations_are_valid_sql(self):
        """Migration files should be valid SQL."""
        migrations_dir = PMOVES_DIR / "supabase" / "migrations"
        if not migrations_dir.exists():
            pytest.skip("Supabase migrations directory not found")

        for sql_file in migrations_dir.glob("*.sql"):
            content = sql_file.read_text()

            # Basic validation - should have SQL statements
            assert any(
                keyword in content.upper()
                for keyword in ["CREATE", "ALTER", "DROP", "INSERT", "UPDATE"]
            ), f"{sql_file.name} doesn't contain SQL statements"


class TestNeo4jConstraints:
    """Test Neo4j has required constraints."""

    def test_neo4j_constraints_exist(self):
        """Neo4j constraint files should exist."""
        neo4j_dir = PMOVES_DIR / "neo4j" / "cypher"
        if not neo4j_dir.exists():
            pytest.skip("Neo4j cypher directory not found")

        constraint_files = list(neo4j_dir.glob("*.cypher"))
        assert len(constraint_files) > 0, "No Neo4j constraint files found"


class TestMeilisearchIndexes:
    """Test Meilisearch indexes are configured."""

    def test_meilisearch_config_exists(self):
        """Meilisearch config should exist."""
        meilisearch_config = PMOVES_DIR / "configs" / "meilisearch"
        if not meilisearch_config.exists():
            pytest.skip("Meilisearch config directory not found")

        config_files = list(meilisearch_config.glob("*.json"))
        assert len(config_files) > 0, "No Meilisearch config files found"


class TestServiceHealth:
    """Test services pass health checks."""

    @pytest.mark.parametrize(
        "service,port,health_path",
        [
            ("agent-zero", 8080, "/healthz"),
            ("archon", 8091, "/healthz"),
            ("channel-monitor", 8097, "/healthz"),
            ("hi-rag-gateway", 8086, "/healthz"),
            ("supaserch", 8099, "/metrics"),
        ],
    )
    def test_service_health_endpoint(self, fresh_deployment, service, port, health_path):
        """Core services should respond to health checks."""
        # This test requires services to be running
        # Skip if services are not up
        try:
            import urllib.request
            import urllib.error

            url = f"http://localhost:{port}{health_path}"
            req = urllib.request.Request(url, method="GET")

            with urllib.request.urlopen(req, timeout=5) as response:
                assert response.status == 200, f"{service} health check failed"
        except (urllib.error.HTTPError, urllib.error.URLError, ConnectionRefusedError):
            pytest.skip(f"{service} is not running on port {port}")


class TestCHITIntegration:
    """Test CHIT integration works correctly."""

    def test_chit_module_imports(self):
        """CHIT module should be importable."""
        try:
            from pmoves.chit import (
                encode_secret_map,
                decode_secret_map,
                load_cgp,
                save_cgp,
            )
        except ImportError as e:
            pytest.fail(f"Failed to import CHIT module: {e}")

    def test_chit_codec_imports(self):
        """CHIT codec module should be importable (backward compat)."""
        try:
            from pmoves.chit.codec import (
                encode_secret_map,
                decode_secret_map,
                load_cgp,
            )
        except ImportError as e:
            pytest.fail(f"Failed to import CHIT codec: {e}")

    def test_chit_encode_decode_roundtrip(self):
        """CHIT should encode and decode correctly."""
        from pmoves.chit import encode_secret_map, decode_secret_map

        test_secrets = {
            "TEST_VAR_1": "test_value_1",
            "TEST_VAR_2": "test_value_2",
            "NEO4J_AUTH": "neo4j/test_password",
        }

        # Encode
        cgp = encode_secret_map(test_secrets, namespace="test")

        # Decode
        decoded = decode_secret_map(cgp)

        # Verify roundtrip
        for key, value in test_secrets.items():
            assert decoded.get(key) == value, f"Roundtrip failed for {key}"


class TestTierValidation:
    """Test tier validation works."""

    def test_validator_imports(self):
        """Validator module should be importable."""
        try:
            from pmoves.tools.env_validator import (
                validate_tier,
                validate_all_tiers,
                TIER_DEFINITIONS,
            )
        except ImportError as e:
            pytest.fail(f"Failed to import validator: {e}")

    def test_all_tiers_defined(self):
        """All 6 tiers should be defined."""
        from pmoves.tools.env_validator import TIER_DEFINITIONS

        expected_tiers = ["data", "api", "llm", "media", "agent", "worker"]
        for tier in expected_tiers:
            assert tier in TIER_DEFINITIONS, f"Tier {tier} not defined"

    def test_tier_definitions_have_required_fields(self):
        """Tier definitions should have required fields."""
        from pmoves.tools.env_validator import TIER_DEFINITIONS

        for tier, definition in TIER_DEFINITIONS.items():
            assert "file" in definition, f"{tier} missing 'file' field"
            assert "description" in definition, f"{tier} missing 'description' field"
            assert definition["file"] == f"env.tier-{tier}"


class TestBackupScript:
    """Test backup script exists and is executable."""

    def test_backup_script_exists(self):
        """Backup script should exist."""
        backup_script = PMOVES_DIR / "scripts" / "backup_for_fresh_start.sh"
        assert backup_script.exists(), f"Backup script not found: {backup_script}"

    def test_backup_script_is_executable(self):
        """Backup script should be executable."""
        backup_script = PMOVES_DIR / "scripts" / "backup_for_fresh_start.sh"
        if not backup_script.exists():
            pytest.skip("Backup script does not exist")

        # On Windows, skip executable check
        if os.name == "nt":
            pytest.skip("Skipping executable check on Windows")

        assert os.access(backup_script, os.X_OK), (
            f"Backup script is not executable: {backup_script}\n"
            f"Run: chmod +x {backup_script}"
        )


class TestMiniCliEnvCommands:
    """Test mini CLI env commands exist."""

    def test_mini_cli_exists(self):
        """Mini CLI should exist."""
        cli = PMOVES_DIR / "tools" / "mini_cli.py"
        assert cli.exists(), f"Mini CLI not found: {cli}"

    def test_env_commands_available(self):
        """Env commands should be available in mini CLI."""
        cli = PMOVES_DIR / "tools" / "mini_cli.py"
        if not cli.exists():
            pytest.skip("Mini CLI does not exist")

        result = subprocess.run(
            [sys.executable, "-m", "pmoves.tools.mini_cli", "env", "--help"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, "Failed to run env --help"

        output = result.stdout + result.stderr
        expected_commands = ["init", "validate", "doctor", "migrate-to-tiers"]
        for cmd in expected_commands:
            assert cmd in output, f"Command '{cmd}' not found in env help"


class TestInfrastructureVolumes:
    """Test infrastructure volumes are properly configured."""

    def test_docker_compose_has_volumes(self):
        """Docker compose should define volumes."""
        import yaml

        compose_file = PMOVES_DIR / "docker-compose.yml"
        if not compose_file.exists():
            pytest.skip("docker-compose.yml does not exist")

        with open(compose_file) as f:
            compose = yaml.safe_load(f)

        volumes = compose.get("volumes", {})
        assert len(volumes) > 0, "No volumes defined in docker-compose.yml"

        # Check for critical volumes (must match docker-compose.yml names)
        critical_volumes = [
            "supabase-data",  # PostgreSQL/Supabase data
            "neo4j-data",     # Neo4j graph database
            "minio-data",     # MinIO object storage
            # Note: qdrant and meilisearch use default storage (no named volumes)
        ]
        for volume in critical_volumes:
            assert volume in volumes, f"Critical volume not defined: {volume}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
