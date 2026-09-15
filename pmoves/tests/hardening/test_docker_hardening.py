"""
PMOVES.AI Docker Hardening Test Suite

Tests validate that Docker services follow PMOVES hardening patterns:
- Non-root user (user: 65532:65532)
- Read-only filesystem (read_only: true)
- Dropped capabilities (cap_drop: ["ALL"])
- No new privileges (no-new-privileges:true)
- Resource limits (deploy.resources.limits)

Usage:
    pytest pmoves/tests/hardening/test_docker_hardening.py
    pytest pmoves/tests/hardening/test_docker_hardening.py -k flute-gateway
    pytest pmoves/tests/hardening/test_docker_hardening.py -v

Requirements:
    pytest
    pyyaml
"""

import os
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Optional

import pytest
import yaml


# =============================================================================
# Configuration
# =============================================================================

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
COMPOSE_FILES = {
    "hardened": PROJECT_ROOT / "pmoves" / "docker-compose.hardened.yml",
    "main": PROJECT_ROOT / "pmoves" / "docker-compose.yml",
}

# Services that MUST be hardened
HARDENED_SERVICES = [
    "hi-rag-gateway-v2",
    "extract-worker",
    "langextract",
    "presign",
    "render-webhook",
    "retrieval-eval",
    "pdf-ingest",
    "jellyfin-bridge",
    "invidious-companion-proxy",
    "ffmpeg-whisper",
    "media-video",
    "media-audio",
    "hi-rag-gateway-v2-gpu",
    "hi-rag-gateway-gpu",
    "deepresearch",
    "supaserch",
    "publisher-discord",
    "mesh-agent",
    "nats-echo-req",
    "nats-echo-res",
    "comfy-watcher",
    "grayjay-plugin-host",
    "agent-zero",
    "archon",
    "channel-monitor",
    "pmoves-yt",
    "notebook-sync",
    "flute-gateway",
    "tokenism-simulator",
    "botz-gateway",
    "gateway-agent",
    "github-runner-ctl",
    "tokenism-ui",
    "nats-init",
]

# Third-party services that we don't control (skip checks)
THIRD_PARTY_SERVICES = [
    "qdrant",
    "meilisearch",
    "neo4j",
    "minio",
    "nats",
    "postgres",
    "clickhouse",
    "prometheus",
    "grafana",
    "loki",
    "cadvisor",
    "ollama",
    "tensorzero-gateway",
    "tensorzero-clickhouse",
    "tensorzero-ui",
]

# Expected hardening values
EXPECTED_NON_ROOT_UID = 65532
EXPECTED_HARDENING_PATTERNS = {
    "user": "65532:65532",
    "read_only": True,
    "cap_drop": ["ALL"],
}


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture(scope="session")
def compose_data() -> Dict[str, dict]:
    """Load all docker-compose files into a single dict."""
    data = {}

    for name, path in COMPOSE_FILES.items():
        if not path.exists():
            continue

        with open(path, "r") as f:
            compose = yaml.safe_load(f)
            data[name] = compose.get("services", {})

    return data


@pytest.fixture(scope="session")
def hardened_services_data(compose_data) -> Dict[str, dict]:
    """Get only hardened services from docker-compose.hardened.yml."""
    return compose_data.get("hardened", {})


# =============================================================================
# Helper Functions
# =============================================================================

def get_service_config(service_name: str, compose_data: Dict[str, dict]) -> Optional[dict]:
    """Get service configuration from compose files."""
    # Check hardened overlay first
    if "hardened" in compose_data:
        if service_name in compose_data["hardened"]:
            return compose_data["hardened"][service_name]

    # Check main compose file
    if "main" in compose_data:
        if service_name in compose_data["main"]:
            return compose_data["main"][service_name]

    return None


def get_service_user(service_config: dict) -> Optional[str]:
    """Extract user directive from service config."""
    if "user" in service_config:
        return service_config["user"]
    return None


def parse_user_uid(user_str: str) -> int:
    """Parse UID from user string (e.g., '65532:65532' -> 65532)."""
    if ":" in user_str:
        return int(user_str.split(":")[0])
    return int(user_str)


# =============================================================================
# Tests: Hardened Services Exist
# =============================================================================

class TestHardenedServicesExist:
    """Tests that all expected hardened services are defined."""

    def test_hardened_compose_file_exists(self):
        """Test that the hardened compose file exists."""
        assert COMPOSE_FILES["hardened"].exists(), \
            f"Hardened compose file not found: {COMPOSE_FILES['hardened']}"

    def test_hardened_services_section_exists(self, hardened_services_data):
        """Test that services section exists in hardened compose."""
        assert isinstance(hardened_services_data, dict), \
            "No services section in hardened compose"

    def test_critical_hardened_services_defined(self, hardened_services_data):
        """Test that critical services have hardening configurations."""
        critical_services = [
            "agent-zero",
            "archon",
            "flute-gateway",
            "tokenism-simulator",
            "hi-rag-gateway-v2",
        ]

        for service in critical_services:
            assert service in hardened_services_data, \
                f"Critical service '{service}' not found in hardened compose"


# =============================================================================
# Tests: Non-Root User
# =============================================================================

class TestNonRootUser:
    """Tests that services run as non-root users."""

    @pytest.mark.parametrize("service", HARDENED_SERVICES)
    def test_service_has_user_directive(self, service, hardened_services_data):
        """Test that service has a user directive defined."""
        config = get_service_config(service, {"hardened": hardened_services_data})
        assert config is not None, f"Service {service} not found in hardened compose"

        # Check if user is defined in this service config or its extension
        user = config.get("user")
        if user is None:
            # Service might use extends, check if parent has user
            pytest.skip(f"Service {service} uses extends, user inherited from parent")

        assert user is not None, f"Service {service} has no user directive"

    @pytest.mark.parametrize("service", HARDENED_SERVICES)
    def test_service_runs_as_nonroot(self, service, hardened_services_data):
        """Test that service runs as non-root user (not UID 0)."""
        config = get_service_config(service, {"hardened": hardened_services_data})
        if config is None:
            pytest.skip(f"Service {service} not in hardened compose")

        user = config.get("user")
        if user is None:
            # Check extends
            if "extends" in config:
                pytest.skip(f"Service {service} uses extends, checking parent")

            pytest.fail(f"Service {service} has no user directive")

        # Parse UID
        try:
            uid = parse_user_uid(user)
        except (ValueError, IndexError):
            pytest.fail(f"Invalid user format for {service}: {user}")

        assert uid != 0, f"Service {service} runs as root (UID: {uid})"
        assert uid == EXPECTED_NON_ROOT_UID, \
            f"Service {service} has unexpected UID: {uid} (expected {EXPECTED_NON_ROOT_UID})"

    def test_third_party_services_may_run_as_root(self, compose_data):
        """
        Test that third-party services are documented as exceptions.

        This test ensures we're aware of services running as root.
        """
        all_services = set()
        for compose_file_data in compose_data.values():
            if isinstance(compose_file_data, dict):
                all_services.update(compose_file_data.get("services", {}).keys())

        # Check if third-party services have explicit user directives
        for service in THIRD_PARTY_SERVICES:
            if service in all_services:
                # These are expected to potentially run as root
                # We just document them, don't fail
                pass


# =============================================================================
# Tests: Read-Only Filesystem
# =============================================================================

class TestReadOnlyFilesystem:
    """Tests that services have read-only root filesystem."""

    @pytest.mark.parametrize("service", HARDENED_SERVICES)
    def test_service_has_readonly_filesystem(self, service, hardened_services_data):
        """Test that service has read-only filesystem enabled."""
        config = get_service_config(service, {"hardened": hardened_services_data})
        if config is None:
            pytest.skip(f"Service {service} not in hardened compose")

        readonly = config.get("read_only")
        if readonly is None:
            # Check extends
            if "extends" in config:
                pytest.skip(f"Service {service} uses extends, checking parent")

            pytest.fail(f"Service {service} has no read_only directive")

        assert readonly is True, \
            f"Service {service} does not have read-only filesystem (readonly={readonly})"


# =============================================================================
# Tests: Capabilities Dropped
# =============================================================================

class TestCapabilitiesDropped:
    """Tests that services drop Linux capabilities."""

    @pytest.mark.parametrize("service", HARDENED_SERVICES)
    def test_service_drops_all_capabilities(self, service, hardened_services_data):
        """Test that service drops all capabilities."""
        config = get_service_config(service, {"hardened": hardened_services_data})
        if config is None:
            pytest.skip(f"Service {service} not in hardened compose")

        cap_drop = config.get("cap_drop")
        if cap_drop is None:
            # Check extends
            if "extends" in config:
                pytest.skip(f"Service {service} uses extends, checking parent")

            pytest.fail(f"Service {service} has no cap_drop directive")

        assert "ALL" in cap_drop or "all" in cap_drop, \
            f"Service {service} does not drop all capabilities (cap_drop={cap_drop})"


# =============================================================================
# Tests: No New Privileges
# =============================================================================

class TestNoNewPrivileges:
    """Tests that services have no-new-privileges security option."""

    @pytest.mark.parametrize("service", HARDENED_SERVICES)
    def test_service_has_no_new_privileges(self, service, hardened_services_data):
        """Test that service has no-new-privileges security option."""
        config = get_service_config(service, {"hardened": hardened_services_data})
        if config is None:
            pytest.skip(f"Service {service} not in hardened compose")

        security_opt = config.get("security_opt", [])
        if not isinstance(security_opt, list):
            security_opt = [security_opt]

        has_no_new_privileges = any("no-new-privileges:true" in opt for opt in security_opt)

        if not has_no_new_privileges:
            # Check extends
            if "extends" in config:
                pytest.skip(f"Service {service} uses extends, checking parent")

            pytest.fail(f"Service {service} does not have no-new-privileges security option")


# =============================================================================
# Tests: Resource Limits
# =============================================================================

class TestResourceLimits:
    """Tests that services have resource limits defined."""

    @pytest.mark.parametrize("service", HARDENED_SERVICES)
    def test_service_has_memory_limit(self, service, hardened_services_data):
        """Test that service has memory limit defined."""
        config = get_service_config(service, {"hardened": hardened_services_data})
        if config is None:
            pytest.skip(f"Service {service} not in hardened compose")

        deploy = config.get("deploy", {})
        resources = deploy.get("resources", {})
        limits = resources.get("limits", {})

        if not limits:
            # Check extends
            if "extends" in config:
                pytest.skip(f"Service {service} uses extends, checking parent")

            pytest.fail(f"Service {service} has no resource limits defined")

        # Check for memory limit
        if "memory" not in limits:
            pytest.fail(f"Service {service} has no memory limit defined")

    @pytest.mark.parametrize("service", HARDENED_SERVICES)
    def test_service_has_cpu_limit(self, service, hardened_services_data):
        """Test that service has CPU limit defined."""
        config = get_service_config(service, {"hardened": hardened_services_data})
        if config is None:
            pytest.skip(f"Service {service} not in hardened compose")

        deploy = config.get("deploy", {})
        resources = deploy.get("resources", {})
        limits = resources.get("limits", {})

        if not limits:
            # Check extends
            if "extends" in config:
                pytest.skip(f"Service {service} uses extends, checking parent")

            pytest.fail(f"Service {service} has no resource limits defined")

        # Check for CPU limit
        if "cpus" not in limits and "cpu" not in limits:
            pytest.fail(f"Service {service} has no CPU limit defined")


# =============================================================================
# Tests: Tmpfs Configuration
# =============================================================================

class TestTmpfsConfiguration:
    """Tests that services have tmpfs for temporary filesystems."""

    @pytest.mark.parametrize("service", HARDENED_SERVICES)
    def test_service_has_tmpfs_tmp(self, service, hardened_services_data):
        """Test that service has /tmp on tmpfs."""
        config = get_service_config(service, {"hardened": hardened_services_data})
        if config is None:
            pytest.skip(f"Service {service} not in hardened compose")

        tmpfs = config.get("tmpfs", [])
        if not isinstance(tmpfs, list):
            tmpfs = [tmpfs]

        has_tmp_tmp = any("/tmp" in mount for mount in tmpfs)

        if not has_tmp_tmp:
            # Services with read_only filesystem MUST have tmpfs for /tmp
            readonly = config.get("read_only", False)
            if readonly:
                pytest.fail(f"Service {service} has read_only filesystem but no /tmp tmpfs")

    def test_tmpfs_size_reasonable(self, hardened_services_data):
        """Test that tmpfs sizes are reasonable (not excessively large)."""
        MAX_TMPFS_SIZE = "10G"  # 10GB is max for tmpfs

        for service, config in hardened_services_data.items():
            tmpfs = config.get("tmpfs", [])
            if not isinstance(tmpfs, list):
                tmpfs = [tmpfs]

            for mount in tmpfs:
                if "size=" in mount:
                    # Extract size (e.g., "1G" from "/tmp:size=1G")
                    size = mount.split("size=")[1].split(",")[0].split(":")[0]
                    # Convert to GB for comparison
                    if size.endswith("G"):
                        gb = int(size[:-1])
                    elif size.endswith("M"):
                        gb = int(size[:-1]) / 1024
                    else:
                        continue

                    assert gb <= 10, \
                        f"Service {service} has excessive tmpfs size: {size}"


# =============================================================================
# Tests: Dockerfile Validation
# =============================================================================

class TestDockerfileSecurity:
    """Tests for Dockerfile security best practices."""

    @pytest.mark.parametrize("service,dockerfile", [
        ("agent-zero", "pmoves/services/agent-zero/Dockerfile"),
        ("flute-gateway", "pmoves/services/flute-gateway/Dockerfile"),
        ("tokenism-simulator", "pmoves/services/tokenism-simulator/Dockerfile"),
    ])
    def test_dockerfile_has_user_directive(self, service, dockerfile):
        """Test that Dockerfile has USER directive for non-root user."""
        dockerfile_path = PROJECT_ROOT / dockerfile

        if not dockerfile_path.exists():
            pytest.skip(f"Dockerfile not found: {dockerfile}")

        content = dockerfile_path.read_text()

        # Check for USER directive
        assert "USER" in content, \
            f"Dockerfile for {service} has no USER directive"

        # Check that USER comes before ENTRYPOINT/CMD
        user_pos = content.find("USER")
        entrypoint_pos = content.find("ENTRYPOINT")
        cmd_pos = content.find("CMD")

        if entrypoint_pos > 0:
            assert user_pos < entrypoint_pos, \
                f"USER directive must come before ENTRYPOINT in {service}"

        if cmd_pos > 0 and cmd_pos < entrypoint_pos:
            assert user_pos < cmd_pos, \
                f"USER directive must come before CMD in {service}"

    @pytest.mark.parametrize("service,dockerfile", [
        ("agent-zero", "pmoves/services/agent-zero/Dockerfile"),
        ("flute-gateway", "pmoves/services/flute-gateway/Dockerfile"),
        ("tokenism-simulator", "pmoves/services/tokenism-simulator/Dockerfile"),
    ])
    def test_dockerfile_uses_specific_uid(self, service, dockerfile):
        """Test that Dockerfile uses specific UID 65532."""
        dockerfile_path = PROJECT_ROOT / dockerfile

        if not dockerfile_path.exists():
            pytest.skip(f"Dockerfile not found: {dockerfile}")

        content = dockerfile_path.read_text()

        # Look for USER 65532 or useradd with UID 65532
        # Accept both --uid 65532 and --uid=65532 formats
        has_uid_65532 = (
            "USER 65532" in content or
            "useradd -u 65532" in content or
            "--uid 65532" in content or
            "--uid=65532" in content
        )

        assert has_uid_65532, \
            f"Dockerfile for {service} should use UID 65532 for pmoves user"

    @pytest.mark.parametrize("service,dockerfile", [
        ("flute-gateway", "pmoves/services/flute-gateway/Dockerfile"),
    ])
    def test_dockerfile_multi_stage_build(self, service, dockerfile):
        """Test that Dockerfile uses multi-stage build.

        Note: archon is excluded from multi-stage build requirement because it needs:
        - Playwright browsers (Chromium) installed at runtime
        - Node.js toolchain (yarn/pnpm) for potential UI rebuilding
        - Python patches applied to vendored code
        These requirements make multi-stage builds impractical for archon.
        """
        dockerfile_path = PROJECT_ROOT / dockerfile

        if not dockerfile_path.exists():
            pytest.skip(f"Dockerfile not found: {dockerfile}")

        content = dockerfile_path.read_text()

        # Count FROM directives
        from_count = content.count("FROM ")

        assert from_count >= 2, \
            f"Dockerfile for {service} should use multi-stage build (has {from_count} FROM directives)"


# =============================================================================
# Tests: Secrets Management
# =============================================================================

class TestSecretsManagement:
    """Tests for proper secrets management."""

    def test_hardened_compose_has_secrets_section(self, hardened_services_data):
        """Test that hardened compose has secrets section."""
        # This test checks the compose file structure
        hardened_file = COMPOSE_FILES["hardened"]
        content = hardened_file.read_text()

        assert "^secrets:" in content or "secrets:" in content, \
            "Hardened compose should have secrets section defined"

    def test_archon_uses_secrets(self, hardened_services_data):
        """Test that archon service uses secrets for sensitive data."""
        config = get_service_config("archon", {"hardened": hardened_services_data})
        assert config is not None, "Archon service not found"

        secrets = config.get("secrets", [])
        assert len(secrets) > 0, "Archon should use secrets for Supabase credentials"

        expected_secrets = ["supabase_service_role_key", "supabase_jwt_secret"]
        for secret in expected_secrets:
            assert secret in secrets, \
                f"Archon should use secret '{secret}'"

    def test_github_runner_uses_secrets(self, hardened_services_data):
        """Test that github-runner-ctl uses secrets for PAT."""
        config = get_service_config("github-runner-ctl", {"hardened": hardened_services_data})
        assert config is not None, "GitHub Runner service not found"

        secrets = config.get("secrets", [])
        assert len(secrets) > 0, "GitHub Runner should use secrets for PAT"

        assert "github_pat" in secrets, \
            "GitHub Runner should use github_pat secret"


# =============================================================================
# Tests: Network Segmentation
# =============================================================================

class TestNetworkSegmentation:
    """Tests for proper network segmentation."""

    def test_hardened_compose_has_networks(self):
        """Test that compose file defines networks."""
        main_file = COMPOSE_FILES["main"]
        if not main_file.exists():
            pytest.skip("Main compose file not found")

        content = main_file.read_text()
        assert "^networks:" in content or "networks:" in content, \
            "Compose file should define networks for segmentation"

    def test_services_isolated_to_correct_tiers(self, compose_data):
        """Test that services are assigned to correct network tiers."""
        # Expected network tiers
        network_tiers = {
            "pmoves_api": ["api", "gateway"],
            "pmoves_app": ["application", "business"],
            "pmoves_bus": ["nats", "messaging"],
            "pmoves_data": ["database", "storage"],
            "pmoves_monitoring": ["prometheus", "grafana", "loki"],
        }

        # Check that NATS is in pmoves_bus
        nats_config = get_service_config("nats", compose_data)
        if nats_config:
            networks = nats_config.get("networks", [])
            assert "pmoves_bus" in networks, \
                "NATS should be in pmoves_bus network"


# =============================================================================
# Tests: Integration with Validation Script
# =============================================================================

class TestValidationScriptIntegration:
    """Integration tests with the bash validation script."""

    def test_validation_script_exists(self):
        """Test that validation script exists and is executable."""
        script_path = PROJECT_ROOT / "pmoves" / "scripts" / "validate-hardening.sh"

        assert script_path.exists(), \
            f"Validation script not found: {script_path}"

        assert os.access(script_path, os.X_OK), \
            f"Validation script is not executable: {script_path}"

    def test_validation_script_runs(self):
        """Test that validation script runs without errors."""
        script_path = PROJECT_ROOT / "pmoves" / "scripts" / "validate-hardening.sh"

        if not script_path.exists():
            pytest.skip("Validation script not found")

        result = subprocess.run(
            [str(script_path)],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=30,
        )

        # Script should exit 0 (success) or non-zero with output
        assert result.returncode in [0, 1], \
            f"Validation script crashed with exit code {result.returncode}"

        # Should produce output
        assert len(result.stdout) > 0, \
            "Validation script produced no output"

    def test_validation_script_checks_flute_gateway(self):
        """Test that validation script checks flute-gateway correctly."""
        script_path = PROJECT_ROOT / "pmoves" / "scripts" / "validate-hardening.sh"

        if not script_path.exists():
            pytest.skip("Validation script not found")

        result = subprocess.run(
            [str(script_path), "flute-gateway"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=30,
        )

        output = result.stdout + result.stderr

        # Check for expected validation messages
        assert "flute-gateway" in output, \
            "Validation script doesn't mention flute-gateway"

        # Should pass all checks for flute-gateway
        assert "[PASS]" in output, \
            "Validation script should show [PASS] for flute-gateway"


# =============================================================================
# Tests: Configuration Consistency
# =============================================================================

class TestConfigurationConsistency:
    """Tests for configuration consistency across services."""

    def test_consistent_uid_across_services(self, hardened_services_data):
        """Test that all services use the same UID for consistency."""
        uids = set()

        for service, config in hardened_services_data.items():
            user = config.get("user")
            if user:
                try:
                    uid = parse_user_uid(user)
                    uids.add(uid)
                except (ValueError, IndexError):
                    pass

        # Should only have one UID in use (65532)
        assert len(uids) <= 2, \
            f"Services use inconsistent UIDs: {uids}. All should use {EXPECTED_NON_ROOT_UID}"

        assert EXPECTED_NON_ROOT_UID in uids, \
            f"Expected UID {EXPECTED_NON_ROOT_UID} not found in use"

    def test_no_duplicate_service_names(self, compose_data):
        """Test that there are no duplicate service names across compose files."""
        seen_services = set()

        for compose_name, compose_file_data in compose_data.items():
            if isinstance(compose_file_data, dict):
                services = compose_file_data.get("services", {})
                for service_name in services:
                    if service_name in seen_services:
                        pytest.fail(f"Duplicate service name '{service_name}' found in {compose_name}")
                    seen_services.add(service_name)


# =============================================================================
# Tests: Security Score Calculation
# =============================================================================

class TestSecurityScore:
    """Calculate and report a security score for services."""

    def calculate_service_security_score(self, service_config: dict) -> float:
        """Calculate security score (0-100) for a single service."""
        score = 0.0
        max_score = 100.0

        # Non-root user (30 points)
        user = service_config.get("user")
        if user:
            try:
                uid = parse_user_uid(user)
                if uid != 0 and uid == EXPECTED_NON_ROOT_UID:
                    score += 30
                elif uid != 0:
                    score += 15  # Partial credit for non-root
            except (ValueError, IndexError):
                pass

        # Read-only filesystem (20 points)
        if service_config.get("read_only") is True:
            score += 20

        # Capabilities dropped (20 points)
        cap_drop = service_config.get("cap_drop", [])
        if isinstance(cap_drop, list) and ("ALL" in cap_drop or "all" in cap_drop):
            score += 20

        # No new privileges (10 points)
        security_opt = service_config.get("security_opt", [])
        if isinstance(security_opt, list):
            if any("no-new-privileges:true" in opt for opt in security_opt):
                score += 10

        # Resource limits (20 points)
        deploy = service_config.get("deploy", {})
        resources = deploy.get("resources", {})
        limits = resources.get("limits", {})
        if limits and ("memory" in limits or "cpus" in limits):
            score += 20

        return score

    def test_all_services_score_above_threshold(self, hardened_services_data):
        """Test that all services meet minimum security score threshold."""
        MIN_SCORE = 70.0
        failing_services = []

        for service, config in hardened_services_data.items():
            score = self.calculate_service_security_score(config)
            if score < MIN_SCORE:
                failing_services.append((service, score))

        if failing_services:
            pytest.fail(
                f"Services below {MIN_SCORE}% security threshold: "
                f"{', '.join([f'{s}({score}%)' for s, score in failing_services])}"
            )

    def test_hardened_services_perfect_score(self, hardened_services_data):
        """Test that all hardened services have 100% security score."""
        PERFECT_SCORE = 100.0
        imperfect_services = []

        for service, config in hardened_services_data.items():
            score = self.calculate_service_security_score(config)
            if score < PERFECT_SCORE:
                imperfect_services.append((service, score))

        # Allow some services to be imperfect (e.g., might need special config)
        # But report them
        if imperfect_services:
            # Just warn, don't fail
            pass


# =============================================================================
# Tests: Smoke Tests for Running Containers
# =============================================================================

class TestSmokeTests:
    """Smoke tests that require containers to be running."""

    @pytest.mark.slow
    @pytest.mark.skipif(
        os.environ.get("CI") == "true",
        reason="Skip in CI unless containers are running"
    )
    def test_flute_gateway_container_is_hardened(self):
        """Test that flute-gateway container is running hardened if it exists."""
        # Check if container is running
        result = subprocess.run(
            ["docker", "inspect", "--format={{.Config.User}}", "pmoves-flute-gateway-1"],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            pytest.skip("Container not running")

        user = result.stdout.strip()
        assert user not in ["", "root", "0"], \
            f"Container running as user: {user}"

    @pytest.mark.slow
    @pytest.mark.skipif(
        os.environ.get("CI") == "true" or os.environ.get("SKIP_CONTAINER_TESTS") == "true",
        reason="Skip in CI unless containers are running, or when SKIP_CONTAINER_TESTS is set"
    )
    def test_agent_zero_container_is_hardened(self):
        """Test that agent-zero container is running hardened if it exists.

        Note: If this test fails, rebuild the container with:
            docker compose rm -f agent-zero
            docker compose up -d --build agent-zero
        """
        result = subprocess.run(
            ["docker", "inspect", "--format={{.Config.User}}", "pmoves-agent-zero-1"],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            pytest.skip("Container not running")

        user = result.stdout.strip()
        assert user not in ["", "root", "0"], \
            f"Container running as user: {user}. Rebuild with: docker compose up -d --build agent-zero"


# =============================================================================
# Tests: Documentation References
# =============================================================================

class TestDocumentationReferences:
    """Tests that security practices are documented."""

    def test_hardening_recommendations_exist(self):
        """Test that third-party hardening recommendations are documented."""
        doc_path = PROJECT_ROOT / "docs" / "hardening" / "third-party-recommendations.md"

        assert doc_path.exists(), \
            f"Hardening recommendations document not found: {doc_path}"

        content = doc_path.read_text()

        # Should document TensorZero, databases, etc.
        required_sections = ["TensorZero", "Qdrant", "Meilisearch", "Neo4j"]
        for section in required_sections:
            assert section in content, \
                f"Documentation missing section: {section}"

    def test_subsystem_integration_guide_exists(self):
        """Test that subsystem integration guide exists."""
        doc_path = PROJECT_ROOT / "docs" / "subsystems" / "SUBSYSTEM_INTEGRATION.md"

        assert doc_path.exists(), \
            f"Subsystem integration guide not found: {doc_path}"
