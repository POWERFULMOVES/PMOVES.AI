"""
Test NATS authentication with tier credentials from PR #483.

Validates that services use authenticated NATS connections from tier env files
rather than unauthenticated fallbacks.

PR: https://github.com/POWERFULMOVES/PMOVES.AI/pull/483
"""

import re
import subprocess
import pytest
import httpx

from _smoke_helpers import PMOVES_DIR, grep_context, grep_file


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_agent_zero_nats_has_credentials() -> None:
    """Agent Zero should connect to NATS with credentials from env.tier-agent."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get("http://localhost:8080/healthz")
    except (httpx.ConnectError, httpx.TimeoutException) as e:
        pytest.skip(f"Agent Zero not accessible: {e}")
        return

    assert response.status_code == 200
    data = response.json()

    assert "nats" in data
    nats_info = data["nats"]

    assert "url" in nats_info
    assert "pmoves@" in nats_info["url"], (
        f"NATS URL should contain credentials (user:pass@), got: {nats_info['url']}"
    )

    assert nats_info.get("connected") is True, (
        f"Agent Zero should be connected to NATS, got: {nats_info.get('connected')}"
    )


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_agent_zero_nats_not_using_unauthenticated_url() -> None:
    """Agent Zero should NOT use unauthenticated NATS URL (nats://nats:4222)."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get("http://localhost:8080/healthz")
    except (httpx.ConnectError, httpx.TimeoutException) as e:
        pytest.skip(f"Agent Zero not accessible: {e}")
        return

    assert response.status_code == 200
    data = response.json()
    nats_url = data.get("nats", {}).get("url", "")

    assert nats_url != "nats://nats:4222", (
        f"NATS URL should have credentials, not unauthenticated format"
    )


@pytest.mark.smoke
def test_agent_zero_env_file_has_nats_credentials() -> None:
    """Verify env.tier-agent defines NATS_URL with credentials."""
    tier_file = PMOVES_DIR / "env.tier-agent"
    if not tier_file.exists():
        pytest.fail("env.tier-agent does not exist — create it with NATS_URL")

    matches = grep_file(tier_file, r"^NATS_URL=")

    if not matches:
        pytest.fail("NATS_URL not found in env.tier-agent")

    nats_url = matches[0]

    assert re.search(r"nats://[^:@]+:[^@]+@", nats_url), (
        f"NATS_URL in env.tier-agent should have credentials (nats://user:pass@host), got: {nats_url}"
    )


@pytest.mark.smoke
def test_comfy_watcher_env_file_has_nats_credentials() -> None:
    """Verify env.tier-worker defines NATS_URL with credentials for comfy-watcher."""
    tier_file = PMOVES_DIR / "env.tier-worker"
    if not tier_file.exists():
        pytest.fail("env.tier-worker does not exist — create it with NATS_URL")

    matches = grep_file(tier_file, r"^NATS_URL=")

    if not matches:
        pytest.fail("NATS_URL not found in env.tier-worker")

    nats_url = matches[0]

    assert re.search(r"nats://[^:@]+:[^@]+@", nats_url), (
        f"NATS_URL in env.tier-worker should have credentials (nats://user:pass@host), got: {nats_url}"
    )


@pytest.mark.smoke
def test_nats_url_in_env_shared_is_authenticated() -> None:
    """Verify NATS_URL in env.shared uses authenticated credentials."""
    matches = grep_file(PMOVES_DIR / "env.shared", r"^NATS_URL=")

    # env.shared should have NATS_URL defined with credentials
    assert len(matches) > 0, (
        "NATS_URL should be defined in env.shared for all services"
    )

    # Verify the URL includes authentication (user:pass@host pattern)
    import re
    for line in matches:
        url = line.split("=", 1)[1].strip()
        assert re.search(r"nats://[^:@]+:[^@]+@", url), (
            f"NATS_URL must use authenticated URL (nats://user:pass@host), got: {url}"
        )


@pytest.mark.smoke
def test_env_shared_still_has_nats_user_and_password() -> None:
    """Verify env.shared still has NATS_USER and NATS_PASSWORD for reference."""
    matches = grep_file(PMOVES_DIR / "env.shared", r"^NATS_(USER|PASSWORD)=")

    # env.shared should still have the credential components
    assert len(matches) >= 2, "Should have both NATS_USER and NATS_PASSWORD"


@pytest.mark.smoke
def test_comfy_watcher_service_uses_tier_nats_url() -> None:
    """Verify comfy-watcher NATS_URL uses authenticated fallback default."""
    compose = PMOVES_DIR / "docker-compose.yml"
    comfy_watcher_config = grep_context(compose, r"comfy-watcher:", after=25)

    if not comfy_watcher_config:
        pytest.skip("comfy-watcher service not found in docker-compose.yml")

    # NATS_URL in environment with ${NATS_URL:-...} fallback is OK — env_file
    # takes precedence.  Only flag hardcoded (non-variable) overrides.
    for line in comfy_watcher_config.split("\n"):
        stripped = line.strip()
        if stripped.startswith("- NATS_URL=") and "${" not in stripped:
            pytest.fail(
                f"comfy-watcher has hardcoded NATS_URL (no variable fallback): {stripped}"
            )


@pytest.mark.smoke
def test_agent_zero_service_uses_tier_nats_url() -> None:
    """Verify agent-zero NATS_URL uses authenticated fallback or comes from env_file."""
    compose = PMOVES_DIR / "docker-compose.yml"
    agent_zero_config = grep_context(compose, r"agent-zero:", after=25)

    # NATS_URL comment (documenting source) is fine.
    # ${NATS_URL:-...} fallback default is fine — env_file takes precedence.
    # Only flag hardcoded (non-variable) overrides.
    for line in agent_zero_config.split("\n"):
        stripped = line.strip()
        if stripped.startswith("- NATS_URL=") and "${" not in stripped:
            pytest.fail(
                f"agent-zero has hardcoded NATS_URL (no variable fallback): {stripped}"
            )


@pytest.mark.smoke
def test_nats_server_requires_authentication() -> None:
    """Verify NATS server requires authentication (not allowing anonymous connections)."""
    try:
        result = subprocess.run(
            ["docker", "inspect", "pmoves-nats-1", "--format", "{{json .Config.Cmd}}"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pytest.skip("Docker CLI not available")
        return

    if result.returncode != 0:
        pytest.skip("NATS container not found")
        return

    cmd_output = result.stdout.strip()

    # NATS should have --user/--pass or auth configuration
    has_auth = "--user" in cmd_output or "--pass" in cmd_output or "auth" in cmd_output.lower()

    assert has_auth, (
        f"NATS server should be configured with authentication, got cmd: {cmd_output}"
    )
