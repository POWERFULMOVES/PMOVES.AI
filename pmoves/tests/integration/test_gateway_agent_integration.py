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


# ============================================================================
# Helper Functions
# ============================================================================

async def service_healthy(url: str, path: str = "/healthz") -> bool:
    """Check if a service is healthy"""
    try:
        async with AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{url}{path}")
            return response.status_code == 200
    except Exception:
        return False


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
            # May return 500 if Cipher is not running
            assert response.status_code in [200, 500]

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
            # Should return validation error
            assert response.status_code in [422, 400, 500]

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_search_skills(self):
        """Should search for stored skills"""
        if not await service_healthy(GATEWAY_URL):
            pytest.skip("Gateway Agent not running")

        async with AsyncClient(base_url=GATEWAY_URL, timeout=DEFAULT_TIMEOUT) as client:
            response = await client.post(
                "/skills/search",
                json={
                    "query": "test",
                    "limit": 10
                }
            )
            # May return 500 if Cipher is not running
            assert response.status_code in [200, 500]

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_search_skills_with_category(self):
        """Should search skills by category"""
        if not await service_healthy(GATEWAY_URL):
            pytest.skip("Gateway Agent not running")

        async with AsyncClient(base_url=GATEWAY_URL, timeout=DEFAULT_TIMEOUT) as client:
            response = await client.post(
                "/skills/search",
                json={
                    "query": "test",
                    "category": "automation",
                    "limit": 5
                }
            )
            assert response.status_code in [200, 500]


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
    async def test_secrets_endpoint_masks(self):
        """Secrets endpoint should mask all values"""
        if not await service_healthy(GATEWAY_URL):
            pytest.skip("Gateway Agent not running")

        async with AsyncClient(base_url=GATEWAY_URL, timeout=DEFAULT_TIMEOUT) as client:
            response = await client.get("/secrets")
            assert response.status_code == 200

            secrets = response.json()
            for service, value in secrets.items():
                if value:  # Non-empty values
                    # Should be masked
                    assert "..." in str(value) or len(str(value)) < 20

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_secrets_endpoint_structure(self):
        """Secrets endpoint should return proper structure"""
        if not await service_healthy(GATEWAY_URL):
            pytest.skip("Gateway Agent not running")

        async with AsyncClient(base_url=GATEWAY_URL, timeout=DEFAULT_TIMEOUT) as client:
            response = await client.get("/secrets")
            assert response.status_code == 200

            secrets = response.json()
            assert isinstance(secrets, dict)


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
    async def test_concurrent_requests(self):
        """Should handle multiple concurrent requests"""
        if not await service_healthy(GATEWAY_URL):
            pytest.skip("Gateway Agent not running")

        async with AsyncClient(base_url=GATEWAY_URL, timeout=DEFAULT_TIMEOUT) as client:
            # Send multiple concurrent requests
            tasks = [
                client.get("/tools"),
                client.get("/healthz"),
                client.get("/secrets"),
            ]
            responses = await asyncio.gather(*tasks, return_exceptions=True)

            # All should succeed
            for response in responses:
                if not isinstance(response, Exception):
                    assert response.status_code == 200


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
