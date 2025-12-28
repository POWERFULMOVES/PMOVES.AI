#!/usr/bin/env python3
"""
Unit Tests for PMOVES Gateway Agent

Tests the Gateway Agent components in isolation:
- ToolRegistry: Tool discovery and caching
- SecretManager: GitHub Secrets management
- API Endpoints: Request/response validation
"""

import asyncio
import os
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient, ASGITransport

# Import Gateway Agent components
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../services/gateway-agent"))

from app import (
    ToolRegistry,
    SecretManager,
    ToolDefinition,
    app,
    tool_registry
)


# ============================================================================
# Test ToolRegistry
# ============================================================================

class TestToolRegistry:
    """Test tool discovery and caching functionality"""

    @pytest.mark.asyncio
    async def test_discover_tools_returns_list(self):
        """Should return list of ToolDefinition objects"""
        # Use force_refresh=False to avoid actual API call
        tools = await tool_registry.discover_tools(force_refresh=False)
        assert isinstance(tools, list)

    @pytest.mark.asyncio
    async def test_fallback_tools_structure(self):
        """Fallback tools should have correct structure"""
        registry = ToolRegistry()
        tools = registry._get_fallback_tools()
        assert isinstance(tools, list)
        assert len(tools) >= 5
        # All tools should be ToolDefinition instances
        for tool in tools:
            assert isinstance(tool, ToolDefinition)
            assert tool.name
            assert tool.description
            assert tool.category
            assert tool.mcp_server

    def test_infer_category_infrastructure(self):
        """Should infer infrastructure category from VPS/DNS related names"""
        registry = ToolRegistry()
        assert registry._infer_category("hostinger_list_vps") == "infrastructure"
        assert registry._infer_category("tailscale_create_route") == "infrastructure"
        assert registry._infer_category("dns_manage_record") == "infrastructure"

    def test_infer_category_automation(self):
        """Should infer automation category from workflow/schedule names"""
        registry = ToolRegistry()
        assert registry._infer_category("n8n_execute_workflow") == "automation"
        assert registry._infer_category("schedule_create_task") == "automation"

    def test_infer_category_vision(self):
        """Should infer vision category from image/video analysis names"""
        registry = ToolRegistry()
        assert registry._infer_category("vl_sentinel_analyze") == "vision"
        assert registry._infer_category("image_process_frame") == "vision"

    def test_infer_category_documents(self):
        """Should infer documents category from PDF/doc related names"""
        registry = ToolRegistry()
        assert registry._infer_category("docling_convert_pdf") == "documents"
        assert registry._infer_category("pdf_extract_text") == "documents"

    def test_infer_category_memory(self):
        """Should infer memory category from store/recall related names"""
        registry = ToolRegistry()
        assert registry._infer_category("cipher_store_memory") == "memory"
        assert registry._infer_category("memory_recall_skill") == "memory"

    def test_infer_category_default(self):
        """Should default to 'general' for unrecognized patterns"""
        registry = ToolRegistry()
        assert registry._infer_category("unknown_random_tool") == "general"

    @pytest.mark.asyncio
    async def test_cache_ttl_respected(self):
        """Should respect cache TTL and not refetch within TTL"""
        registry = ToolRegistry()
        registry.cache_ttl = 60  # 60 seconds

        # First call should populate cache
        await registry.discover_tools(force_refresh=True)
        first_refresh = registry._last_refresh

        # Second call within TTL should use cache
        await registry.discover_tools(force_refresh=False)
        second_refresh = registry._last_refresh

        assert first_refresh == second_refresh

    @pytest.mark.asyncio
    async def test_cache_bypass_with_force_refresh(self):
        """Should bypass cache when force_refresh=True"""
        registry = ToolRegistry()

        # First call
        await registry.discover_tools(force_refresh=True)
        first_refresh = registry._last_refresh

        # Small delay to ensure different timestamp
        await asyncio.sleep(0.01)

        # Force refresh should update timestamp
        await registry.discover_tools(force_refresh=True)
        second_refresh = registry._last_refresh

        assert second_refresh > first_refresh


# ============================================================================
# Test SecretManager
# ============================================================================

class TestSecretManager:
    """Test GitHub Secrets management and credential masking"""

    def test_get_credential_from_env(self, monkeypatch):
        """Should retrieve credential from environment variable"""
        monkeypatch.setenv("HOSTINGER_API_KEY", "test-key-12345")
        assert SecretManager.get_credential("hostinger") == "test-key-12345"

    def test_get_credential_tailscale_authkey(self, monkeypatch):
        """Should handle TAILSCALE_AUTHKEY specially"""
        monkeypatch.setenv("TAILSCALE_AUTHKEY", "ts-key-xyz")
        assert SecretManager.get_credential("tailscale") == "ts-key-xyz"

    def test_get_credential_missing(self, monkeypatch):
        """Should return None for missing credentials"""
        # Ensure no hostinger key is set
        monkeypatch.delenv("HOSTINGER_API_KEY", raising=False)
        assert SecretManager.get_credential("hostinger") is None or SecretManager.get_credential("hostinger") == ""

    def test_get_all_credentials_masks_values(self, monkeypatch):
        """Should mask sensitive values in credentials list"""
        monkeypatch.setenv("HOSTINGER_API_KEY", "my-secret-key-12345678")
        creds = SecretManager.get_all_credentials()
        assert "hostinger" in creds
        assert creds["hostinger"].endswith("...")
        assert "12345678" not in creds["hostinger"]

    def test_get_all_credentials_short_masking(self, monkeypatch):
        """Should handle short credentials with minimal masking"""
        monkeypatch.setenv("HOSTINGER_API_KEY", "short")
        creds = SecretManager.get_all_credentials()
        assert creds["hostinger"] == "***" or creds["hostinger"] == "short..."

    def test_secrets_map_coverage(self):
        """All services in SECRETS_MAP should have corresponding env vars"""
        for env_var, service in SecretManager.SECRETS_MAP.items():
            # Verify the pattern is consistent
            # Note: Tailscale has both AUTHKEY and API_KEY
            # Note: Cipher uses VENICE_API_KEY (different service name)
            assert env_var.startswith("TAILSCALE") or env_var == "VENICE_API_KEY" or env_var == f"{service.upper()}_API_KEY"

    def test_get_all_credentials_filters_empty(self, monkeypatch):
        """Should only return credentials that are actually set"""
        monkeypatch.setenv("HOSTINGER_API_KEY", "key1")
        # Don't set other keys
        creds = SecretManager.get_all_credentials()
        # Should have at least hostinger
        assert "hostinger" in creds


# ============================================================================
# Test Health Endpoint
# ============================================================================

class TestHealthEndpoint:
    """Test health check endpoint"""

    @pytest.mark.asyncio
    async def test_healthz_returns_status(self):
        """Should return health status with service availability"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/healthz")
            assert response.status_code == 200
            data = response.json()
            assert "status" in data
            assert "timestamp" in data
            assert "services" in data

    @pytest.mark.asyncio
    async def test_healthz_status_values(self):
        """Status should be either 'healthy' or 'degraded'"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/healthz")
            data = response.json()
            assert data["status"] in ["healthy", "degraded"]

    @pytest.mark.asyncio
    async def test_healthz_services_dict(self):
        """Should return services health dict"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/healthz")
            data = response.json()
            services = data["services"]
            assert isinstance(services, dict)
            # Should have keys for known services
            expected_keys = ["agent_zero", "cipher", "tensorzero"]
            for key in expected_keys:
                assert key in services


# ============================================================================
# Test Tools Endpoint
# ============================================================================

class TestToolsEndpoint:
    """Test tools API endpoints"""

    @pytest.mark.asyncio
    async def test_list_tools_all(self):
        """Should list all tools without category filter"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/tools")
            assert response.status_code == 200
            data = response.json()
            assert "total" in data
            assert "tools" in data
            assert "categories" in data
            assert data["total"] >= 0

    @pytest.mark.asyncio
    async def test_list_tools_response_structure(self):
        """Should return properly structured tools response"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/tools")
            data = response.json()
            # Check structure
            assert isinstance(data["tools"], list)
            assert isinstance(data["categories"], dict)
            assert isinstance(data["total"], int)

    @pytest.mark.asyncio
    async def test_list_tools_by_category_automation(self):
        """Should filter tools by automation category"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/tools?category=automation")
            assert response.status_code == 200
            data = response.json()
            # All returned tools should match category
            for tool in data["tools"]:
                assert tool["category"] == "automation"

    @pytest.mark.asyncio
    async def test_list_tools_by_category_infrastructure(self):
        """Should filter tools by infrastructure category"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/tools?category=infrastructure")
            assert response.status_code == 200
            data = response.json()
            for tool in data["tools"]:
                assert tool["category"] == "infrastructure"

    @pytest.mark.asyncio
    async def test_list_tools_force_refresh(self):
        """Should accept force_refresh parameter"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/tools?force_refresh=true")
            assert response.status_code == 200


# ============================================================================
# Test Tool Execution
# ============================================================================

class TestToolExecution:
    """Test tool execution endpoint"""

    @pytest.mark.asyncio
    async def test_execute_tool_missing_tool(self):
        """Should return error for non-existent tool"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/tools/execute",
                json={
                    "tool_name": "nonexistent_tool",
                    "parameters": {}
                }
            )
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is False
            assert "error" in data

    @pytest.mark.asyncio
    async def test_execute_tool_valid_request(self):
        """Should accept valid execution request"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/tools/execute",
                json={
                    "tool_name": "test_tool",
                    "parameters": {"key": "value"},
                    "timeout": 30
                }
            )
            # Will fail to find tool, but request format is valid
            assert response.status_code == 200


# ============================================================================
# Test Secrets Endpoint
# ============================================================================

class TestSecretsEndpoint:
    """Test secrets listing endpoint"""

    @pytest.mark.asyncio
    async def test_list_secrets_returns_dict(self):
        """Should return dictionary of secrets"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/secrets")
            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, dict)

    @pytest.mark.asyncio
    async def test_list_secrets_masks_values(self):
        """Secret values should be masked in response"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/secrets")
            data = response.json()
            # All values should be masked if present
            for value in data.values():
                if value:  # Non-empty values
                    assert "..." in value or len(value) < 20


# ============================================================================
# Test Skills Endpoints
# ============================================================================

class TestSkillsEndpoints:
    """Test skills storage and search endpoints"""

    @pytest.mark.asyncio
    async def test_store_skill_accepts_valid_data(self):
        """Should accept valid skill storage request"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/skills/store",
                json={
                    "name": "test_skill",
                    "description": "Test skill",
                    "category": "test",
                    "pattern": "Input → Output",
                    "outcome": "Success",
                    "mcp_tool": "test:tool"
                }
            )
            # Will fail if Cipher is down, but request format is valid
            assert response.status_code in [200, 500]

    @pytest.mark.asyncio
    async def test_search_skills_accepts_valid_data(self):
        """Should accept valid skill search request"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/skills/search",
                json={
                    "query": "test",
                    "limit": 10
                }
            )
            # Will fail if Cipher is down, but request format is valid
            assert response.status_code in [200, 500]


# ============================================================================
# Test Data Models
# ============================================================================

class TestDataModels:
    """Test Pydantic data models"""

    def test_tool_definition_creation(self):
        """Should create valid ToolDefinition"""
        tool = ToolDefinition(
            name="test_tool",
            description="Test tool description",
            category="test",
            mcp_server="test-server",
            parameters={"key": "value"},
            enabled=True
        )
        assert tool.name == "test_tool"
        assert tool.description == "Test tool description"
        assert tool.category == "test"
        assert tool.mcp_server == "test-server"
        assert tool.parameters == {"key": "value"}
        assert tool.enabled is True

    def test_tool_definition_defaults(self):
        """Should use default values for optional fields"""
        tool = ToolDefinition(
            name="test_tool",
            description="Test",
            category="test",
            mcp_server="test"
        )
        assert tool.parameters == {}
        assert tool.enabled is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
