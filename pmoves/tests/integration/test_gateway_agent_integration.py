#!/usr/bin/env python3
"""
Integration Tests for PMOVES Gateway Agent

Tests Gateway Agent integration with real PMOVES services:
- Agent Zero MCP API (port 8080)
- Cipher Memory (port 3025)
- TensorZero Gateway (port 3030)
- Supabase (port 3010)

These tests require services to be running.
Run with: pytest -m integration pmoves/tests/integration/test_gateway_agent_integration.py
"""

import asyncio
import os
from typing import Dict, Any

import pytest
from httpx import AsyncClient, TimeoutException


# ============================================================================
# Configuration
# ============================================================================

GATEWAY_URL = os.environ.get("GATEWAY_URL", "http://localhost:8100")
AGENT_ZERO_URL = os.environ.get("AGENT_ZERO_URL", "http://localhost:8080")
CIPHER_URL = os.environ.get("CIPHER_URL", "http://localhost:3025")
TENSORZERO_URL = os.environ.get("TENSORZERO_URL", "http://localhost:3030")

# Test timeout for integration tests
DEFAULT_TIMEOUT = 30.0

# Test API key for integration tests (should match GATEWAY_API_KEY in env)
TEST_API_KEY = os.environ.get("GATEWAY_API_KEY", "test-key-for-testing")


# ============================================================================
# Helper Functions
# ============================================================================

async def service_healthy(url: str, path: str = "/healthz") -> bool:
    """Check if a service is healthy. Logs reason for failure."""
    try:
        async with AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{url}{path}")
            return response.status_code == 200
    except TimeoutException:
        print(f"[WARN] Timeout checking {url}{path}")
        return False
    except httpx.ConnectError as e:
        print(f"[WARN] Connection failed to {url}{path}: {e}")
        return False
    except Exception as e:
        print(f"[WARN] Health check failed for {url}{path}: {type(e).__name__}: {e}")
        return False


# ============================================================================
# Pytest Fixtures
# ============================================================================

@pytest.fixture
async def authenticated_client():
    """
    Return async client with valid API key header for testing.

    Note: If GATEWAY_API_KEY env var is unset, authentication is disabled
    for development. This fixture will still work but tests may not
    properly validate auth behavior.
    """
    if not await service_healthy(GATEWAY_URL):
        pytest.skip("Gateway Agent not running")

    headers = {"X-Gateway-API-Key": TEST_API_KEY}
    async with AsyncClient(base_url=GATEWAY_URL, timeout=DEFAULT_TIMEOUT, headers=headers) as client:
        yield client


@pytest.fixture
async def unauthenticated_client():
    """Return async client without API key for testing auth requirements."""
    if not await service_healthy(GATEWAY_URL):
        pytest.skip("Gateway Agent not running")

    async with AsyncClient(base_url=GATEWAY_URL, timeout=DEFAULT_TIMEOUT) as client:
        yield client


# ============================================================================
# Test Suite: Service Health
# ============================================================================

class TestServiceHealth:
    """Verify all required services are running before integration tests"""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_gateway_agent_accessible(self):
        """Gateway Agent should be accessible"""
        healthy = await service_healthy(GATEWAY_URL)
        if not healthy:
            pytest.skip("Gateway Agent not running")
        assert healthy

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_agent_zero_accessible(self):
        """Agent Zero should be accessible"""
        healthy = await service_healthy(AGENT_ZERO_URL)
        if not healthy:
            pytest.skip("Agent Zero not running")
        assert healthy

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_tensorzero_accessible(self):
        """TensorZero Gateway should be accessible"""
        healthy = await service_healthy(TENSORZERO_URL)
        if not healthy:
            pytest.skip("TensorZero not running")
        assert healthy

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_cipher_accessible(self):
        """Cipher Memory should be accessible"""
        healthy = await service_healthy(CIPHER_URL, "/health")
        if not healthy:
            pytest.skip("Cipher Memory not running")
        assert healthy


# ============================================================================
# Test Suite: Tool Discovery
# ============================================================================

class TestToolDiscovery:
    """Test tool discovery from Agent Zero MCP"""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_discover_tools_from_gateway(self):
        """Should discover tools via Gateway Agent"""
        if not await service_healthy(GATEWAY_URL):
            pytest.skip("Gateway Agent not running")

        async with AsyncClient(base_url=GATEWAY_URL, timeout=DEFAULT_TIMEOUT) as client:
            response = await client.get("/tools")
            assert response.status_code == 200

            data = response.json()
            assert "total" in data
            assert "tools" in data
            assert "categories" in data

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_tools_have_required_fields(self):
        """Discovered tools should have all required fields"""
        if not await service_healthy(GATEWAY_URL):
            pytest.skip("Gateway Agent not running")

        async with AsyncClient(base_url=GATEWAY_URL, timeout=DEFAULT_TIMEOUT) as client:
            response = await client.get("/tools")
            assert response.status_code == 200

            data = response.json()
            for tool in data["tools"]:
                assert "name" in tool
                assert "description" in tool
                assert "category" in tool
                assert "mcp_server" in tool

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_tools_category_filter(self):
        """Should filter tools by category"""
        if not await service_healthy(GATEWAY_URL):
            pytest.skip("Gateway Agent not running")

        async with AsyncClient(base_url=GATEWAY_URL, timeout=DEFAULT_TIMEOUT) as client:
            # Test automation category
            response = await client.get("/tools?category=automation")
            assert response.status_code == 200

            data = response.json()
            for tool in data["tools"]:
                assert tool["category"] == "automation"

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_tool_cache_refresh(self):
        """Force refresh should update tool cache"""
        if not await service_healthy(GATEWAY_URL):
            pytest.skip("Gateway Agent not running")

        async with AsyncClient(base_url=GATEWAY_URL, timeout=DEFAULT_TIMEOUT) as client:
            # First call
            response1 = await client.get("/tools")
            assert response1.status_code == 200

            # Force refresh
            response2 = await client.get("/tools?force_refresh=true")
            assert response2.status_code == 200

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_fallback_tools_when_agent_zero_down(self):
        """Should return fallback tools when Agent Zero is unreachable"""
        # This test uses a mock Agent Zero URL to simulate downtime
        if not await service_healthy(GATEWAY_URL):
            pytest.skip("Gateway Agent not running")

        # Note: We can't easily mock this in integration tests
        # This would require restarting Gateway with different env vars
        # Skip for now
        pytest.skip("Requires Gateway with AGENT_ZERO_URL pointing to non-existent service")


# ============================================================================
# Test Suite: Tool Execution
# ============================================================================

class TestToolExecution:
    """Test tool execution via Gateway"""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_execute_tool_response_format(self):
        """Tool execution should return proper response format"""
        if not await service_healthy(GATEWAY_URL):
            pytest.skip("Gateway Agent not running")

        async with AsyncClient(base_url=GATEWAY_URL, timeout=DEFAULT_TIMEOUT) as client:
            # Try to execute a tool (will likely fail if tool doesn't exist)
            response = await client.post(
                "/tools/execute",
                json={
                    "tool_name": "test:unknown_tool",
                    "parameters": {},
                    "timeout": 5
                }
            )
            assert response.status_code == 200

            data = response.json()
            assert "success" in data
            assert "result" in data
            assert "error" in data
            assert "execution_time_ms" in data

            # Verify semantics: success field should be boolean
            assert isinstance(data["success"], bool)
            # If tool execution failed, error should be populated
            if not data["success"]:
                assert data["error"] is not None

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_execute_nonexistent_tool(self):
        """Should return error for non-existent tool"""
        if not await service_healthy(GATEWAY_URL):
            pytest.skip("Gateway Agent not running")

        async with AsyncClient(base_url=GATEWAY_URL, timeout=DEFAULT_TIMEOUT) as client:
            response = await client.post(
                "/tools/execute",
                json={
                    "tool_name": "nonexistent:tool",
                    "parameters": {}
                }
            )
            assert response.status_code == 200

            data = response.json()
            assert data["success"] is False
            assert data["error"] is not None

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_execute_with_timeout(self):
        """Should respect timeout parameter"""
        if not await service_healthy(GATEWAY_URL):
            pytest.skip("Gateway Agent not running")

        async with AsyncClient(base_url=GATEWAY_URL, timeout=DEFAULT_TIMEOUT) as client:
            start = asyncio.get_event_loop().time()

            response = await client.post(
                "/tools/execute",
                json={
                    "tool_name": "test:unknown_tool",
                    "parameters": {},
                    "timeout": 1  # Very short timeout
                }
            )

            elapsed = asyncio.get_event_loop().time() - start
            assert response.status_code == 200
            # Should return quickly even for unknown tool
            assert elapsed < 5


# ============================================================================
# Test Suite: Skills Storage
# ============================================================================

class TestSkillsStorage:
    """Test skills storage and retrieval via Cipher Memory"""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_store_skill_request_format(self):
        """Should accept skill storage request"""
        if not await service_healthy(GATEWAY_URL):
            pytest.skip("Gateway Agent not running")
        if not await service_healthy(CIPHER_URL, "/health"):
            pytest.skip("Cipher Memory not running")

        async with AsyncClient(base_url=GATEWAY_URL, timeout=DEFAULT_TIMEOUT) as client:
            response = await client.post(
                "/skills/store",
                json={
                    "name": f"integration_test_skill_{os.getpid()}",
                    "description": "Created by integration test",
                    "category": "test",
                    "pattern": "Test pattern → Test outcome",
                    "outcome": "Test success",
                    "mcp_tool": "test:integration"
                }
            )
            # Should succeed when all dependencies are healthy
            assert response.status_code == 200

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_store_skill_missing_fields(self):
        """Should validate required fields"""
        if not await service_healthy(GATEWAY_URL):
            pytest.skip("Gateway Agent not running")

        async with AsyncClient(base_url=GATEWAY_URL, timeout=DEFAULT_TIMEOUT) as client:
            # Missing required fields
            response = await client.post(
                "/skills/store",
                json={
                    "name": "incomplete_skill"
                    # Missing other required fields
                }
            )
            # Should return validation error (422 FastAPI validation, 400 bad request)
            assert response.status_code in [400, 422]

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_search_skills(self):
        """Should search for stored skills"""
        if not await service_healthy(GATEWAY_URL):
            pytest.skip("Gateway Agent not running")
        if not await service_healthy(CIPHER_URL, "/health"):
            pytest.skip("Cipher Memory not running")

        async with AsyncClient(base_url=GATEWAY_URL, timeout=DEFAULT_TIMEOUT) as client:
            response = await client.post(
                "/skills/search",
                json={
                    "query": "test",
                    "limit": 10
                }
            )
            # Should succeed when all dependencies are healthy
            assert response.status_code == 200

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_search_skills_with_category(self):
        """Should search skills by category"""
        if not await service_healthy(GATEWAY_URL):
            pytest.skip("Gateway Agent not running")
        if not await service_healthy(CIPHER_URL, "/health"):
            pytest.skip("Cipher Memory not running")

        async with AsyncClient(base_url=GATEWAY_URL, timeout=DEFAULT_TIMEOUT) as client:
            response = await client.post(
                "/skills/search",
                json={
                    "query": "test",
                    "category": "automation",
                    "limit": 5
                }
            )
            # Should succeed when all dependencies are healthy
            assert response.status_code == 200


# ============================================================================
# Test Suite: Health & Metrics
# ============================================================================

class TestHealthAndMetrics:
    """Test health checks and metrics endpoints"""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_health_check_comprehensive(self):
        """Health check should report status of all dependencies"""
        if not await service_healthy(GATEWAY_URL):
            pytest.skip("Gateway Agent not running")

        async with AsyncClient(base_url=GATEWAY_URL, timeout=DEFAULT_TIMEOUT) as client:
            response = await client.get("/healthz")
            assert response.status_code == 200

            data = response.json()
            assert "status" in data
            assert "services" in data

            # Check individual service status
            services = data["services"]
            expected_services = ["agent_zero", "cipher", "tensorzero"]
            for service in expected_services:
                assert service in services

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_secrets_endpoint_masks(self, authenticated_client):
        """Secrets endpoint should mask all values (with authentication)"""
        response = await authenticated_client.get("/secrets")
        assert response.status_code == 200

        secrets = response.json()
        for service, value in secrets.items():
            if value:  # Non-empty values
                value_str = str(value)
                # Masked values should end with "..." and be short
                # Format from app.py:350 is value[:8] + "..."
                assert "..." in value_str, f"Value for {service} should be masked with '...'"
                # Masked values should be 11 chars or less (8 + "...")
                assert len(value_str) <= 11, f"Masked value for {service} too long: {len(value_str)}"

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_secrets_endpoint_structure(self, authenticated_client):
        """Secrets endpoint should return proper structure (with authentication)"""
        response = await authenticated_client.get("/secrets")
        assert response.status_code == 200

        secrets = response.json()
        assert isinstance(secrets, dict)

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_secrets_endpoint_requires_auth(self, unauthenticated_client):
        """Secrets endpoint should return 403 without API key"""
        response = await unauthenticated_client.get("/secrets")
        # Should return 403 Forbidden when no API key is provided
        assert response.status_code == 403

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_secrets_endpoint_rejects_invalid_key(self, unauthenticated_client):
        """Secrets endpoint should return 403 with wrong API key"""
        response = await unauthenticated_client.get(
            "/secrets",
            headers={"X-Gateway-API-Key": "wrong-api-key-12345"}
        )
        assert response.status_code == 403


# ============================================================================
# Test Suite: End-to-End Workflows
# ============================================================================

class TestEndToEndWorkflows:
    """Test complete workflows through Gateway Agent"""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_discovery_to_execution_workflow(self):
        """Complete workflow: discover tools, select one, execute"""
        if not await service_healthy(GATEWAY_URL):
            pytest.skip("Gateway Agent not running")

        async with AsyncClient(base_url=GATEWAY_URL, timeout=DEFAULT_TIMEOUT) as client:
            # Step 1: Discover tools
            discover_response = await client.get("/tools")
            assert discover_response.status_code == 200
            tools_data = discover_response.json()

            # Step 2: Try to execute first tool (will likely fail but tests the path)
            if tools_data["tools"]:
                first_tool = tools_data["tools"][0]["name"]
                exec_response = await client.post(
                    "/tools/execute",
                    json={
                        "tool_name": first_tool,
                        "parameters": {}
                    }
                )
                assert exec_response.status_code == 200

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_category_browse_workflow(self):
        """Browse tools by category"""
        if not await service_healthy(GATEWAY_URL):
            pytest.skip("Gateway Agent not running")

        async with AsyncClient(base_url=GATEWAY_URL, timeout=DEFAULT_TIMEOUT) as client:
            # Get all tools to see categories
            response = await client.get("/tools")
            assert response.status_code == 200
            data = response.json()

            # Browse each category
            for category in data["categories"].keys():
                cat_response = await client.get(f"/tools?category={category}")
                assert cat_response.status_code == 200
                cat_data = cat_response.json()
                # All tools should be in requested category
                for tool in cat_data["tools"]:
                    assert tool["category"] == category

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_health_dependency_workflow(self):
        """Check health, then test dependent services"""
        if not await service_healthy(GATEWAY_URL):
            pytest.skip("Gateway Agent not running")

        async with AsyncClient(base_url=GATEWAY_URL, timeout=DEFAULT_TIMEOUT) as client:
            # Check health
            health_response = await client.get("/healthz")
            assert health_response.status_code == 200
            health_data = health_response.json()

            # If Agent Zero is healthy, try tool discovery
            if health_data["services"].get("agent_zero") == "healthy":
                tools_response = await client.get("/tools")
                assert tools_response.status_code == 200


# ============================================================================
# Test Suite: Error Handling
# ============================================================================

class TestErrorHandling:
    """Test error handling and edge cases"""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_invalid_json_request(self):
        """Should handle invalid JSON gracefully"""
        if not await service_healthy(GATEWAY_URL):
            pytest.skip("Gateway Agent not running")

        async with AsyncClient(base_url=GATEWAY_URL, timeout=DEFAULT_TIMEOUT) as client:
            # Note: httpx will validate JSON before sending
            # This tests that the API handles malformed requests
            response = await client.post(
                "/tools/execute",
                json={},  # Empty but valid JSON
                headers={"Content-Type": "application/json"}
            )
            # Should return validation error
            assert response.status_code in [200, 422]

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_concurrent_requests(self, authenticated_client):
        """Should handle multiple concurrent requests (authenticated)"""
        # Send multiple concurrent requests using the authenticated client
        tasks = [
            authenticated_client.get("/tools"),
            authenticated_client.get("/healthz"),
            authenticated_client.get("/secrets"),
        ]
        responses = await asyncio.gather(*tasks, return_exceptions=True)

        # Check that no exceptions occurred
        exceptions = [r for r in responses if isinstance(r, Exception)]
        assert not exceptions, f"Concurrent requests failed with exceptions: {exceptions}"

        # All should succeed
        for response in responses:
            assert isinstance(response, httpx.Response), f"Got exception: {response}"
            assert response.status_code == 200

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_concurrent_mixed_auth_states(self):
        """Should handle concurrent requests with mixed auth states"""
        if not await service_healthy(GATEWAY_URL):
            pytest.skip("Gateway Agent not running")

        valid_key = os.environ.get("GATEWAY_API_KEY", "test-key-for-testing")

        async with AsyncClient(base_url=GATEWAY_URL, timeout=DEFAULT_TIMEOUT) as client:
            tasks = [
                # Valid auth
                client.get("/secrets", headers={"X-Gateway-API-Key": valid_key}),
                # No auth
                client.get("/secrets"),
                # Invalid auth
                client.get("/secrets", headers={"X-Gateway-API-Key": "wrong-key"}),
                # Valid auth
                client.get("/secrets", headers={"X-Gateway-API-Key": valid_key}),
            ]
            responses = await asyncio.gather(*tasks, return_exceptions=True)

            # Handle auth-disabled mode (when GATEWAY_API_KEY not set)
            auth_enabled = os.environ.get("GATEWAY_API_KEY") is not None

            if auth_enabled:
                # First and last should succeed (200)
                assert responses[0].status_code == 200
                assert responses[3].status_code == 200
                # Middle two should fail (403)
                assert responses[1].status_code == 403
                assert responses[2].status_code == 403
            else:
                # All succeed when auth disabled
                for r in responses:
                    if not isinstance(r, Exception):
                        assert r.status_code == 200


# ============================================================================
# Test Suite: OpenAPI Documentation
# ============================================================================

class TestOpenAPIDocumentation:
    """Test OpenAPI schema and documentation"""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_openapi_schema(self):
        """Should provide valid OpenAPI schema"""
        if not await service_healthy(GATEWAY_URL):
            pytest.skip("Gateway Agent not running")

        async with AsyncClient(base_url=GATEWAY_URL, timeout=DEFAULT_TIMEOUT) as client:
            response = await client.get("/openapi.json")
            assert response.status_code == 200

            schema = response.json()
            assert "openapi" in schema
            assert "info" in schema
            assert "paths" in schema

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_openapi_paths_documented(self):
        """All endpoints should be documented in OpenAPI"""
        if not await service_healthy(GATEWAY_URL):
            pytest.skip("Gateway Agent not running")

        async with AsyncClient(base_url=GATEWAY_URL, timeout=DEFAULT_TIMEOUT) as client:
            response = await client.get("/openapi.json")
            assert response.status_code == 200

            schema = response.json()
            paths = schema["paths"]

            # Check key endpoints are documented
            expected_paths = ["/healthz", "/tools", "/tools/execute", "/secrets"]
            for path in expected_paths:
                assert path in paths or f"{path}" in paths


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "integration"])
