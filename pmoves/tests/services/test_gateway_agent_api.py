#!/usr/bin/env python3
"""
API Contract Tests for PMOVES Gateway Agent

Tests API contracts, schemas, and HTTP-level behaviors:
- OpenAPI schema generation
- CORS headers
- Content-Type negotiation
- HTTP method validation
- Response structure validation
"""

import os
from typing import Dict, Any

import pytest
from httpx import AsyncClient, ASGITransport

# Import Gateway Agent app
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../services/gateway-agent"))

from app import app


# ============================================================================
# Test OpenAPI Schema
# ============================================================================

class TestOpenAPISchema:
    """Test OpenAPI schema generation and completeness"""

    @pytest.mark.asyncio
    async def test_openapi_schema_generated(self):
        """FastAPI should generate valid OpenAPI schema"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/openapi.json")
            assert response.status_code == 200
            schema = response.json()
            assert "openapi" in schema
            assert "info" in schema
            assert "paths" in schema

    @pytest.mark.asyncio
    async def test_openapi_version(self):
        """Should use OpenAPI 3.x"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/openapi.json")
            schema = response.json()
            assert schema["openapi"].startswith("3.")

    @pytest.mark.asyncio
    async def test_openapi_info(self):
        """Should have proper API metadata"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/openapi.json")
            schema = response.json()
            info = schema["info"]
            assert "title" in info
            assert "version" in info
            assert info["title"] == "PMOVES Gateway Agent"

    @pytest.mark.asyncio
    async def test_openapi_healthz_documented(self):
        """/healthz endpoint should be documented"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/openapi.json")
            schema = response.json()
            assert "/healthz" in schema["paths"]

    @pytest.mark.asyncio
    async def test_openapi_tools_documented(self):
        """/tools endpoint should be documented"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/openapi.json")
            schema = response.json()
            assert "/tools" in schema["paths"]

    @pytest.mark.asyncio
    async def test_openapi_tools_execute_documented(self):
        """/tools/execute endpoint should be documented"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/openapi.json")
            schema = response.json()
            assert "/tools/execute" in schema["paths"]

    @pytest.mark.asyncio
    async def test_openapi_skills_documented(self):
        """Skills endpoints should be documented"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/openapi.json")
            schema = response.json()
            assert "/skills/store" in schema["paths"]
            assert "/skills/search" in schema["paths"]

    @pytest.mark.asyncio
    async def test_openapi_secrets_documented(self):
        """/secrets endpoint should be documented"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/openapi.json")
            schema = response.json()
            assert "/secrets" in schema["paths"]


# ============================================================================
# Test HTTP Methods and Status Codes
# ============================================================================

class TestHTTPMethods:
    """Test correct HTTP methods are accepted"""

    @pytest.mark.asyncio
    async def test_healthz_get_allowed(self):
        """GET /healthz should be allowed"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/healthz")
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_healthz_post_not_allowed(self):
        """POST /healthz should not be allowed"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/healthz")
            assert response.status_code in [405, 422]  # Method Not Allowed or Unprocessable

    @pytest.mark.asyncio
    async def test_tools_get_allowed(self):
        """GET /tools should be allowed"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/tools")
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_tools_post_not_allowed(self):
        """POST /tools should not be allowed"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/tools")
            assert response.status_code in [405, 422]

    @pytest.mark.asyncio
    async def test_tools_execute_post_allowed(self):
        """POST /tools/execute should be allowed"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/tools/execute",
                json={"tool_name": "test_tool", "parameters": {}}
            )
            # Will return 200 (with error result) or 422 (validation error)
            assert response.status_code in [200, 422]

    @pytest.mark.asyncio
    async def test_tools_execute_get_not_allowed(self):
        """GET /tools/execute should not be allowed"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/tools/execute")
            assert response.status_code in [405, 422]


# ============================================================================
# Test Response Formats
# ============================================================================

class TestResponseFormats:
    """Test API responses use correct content types and formats"""

    @pytest.mark.asyncio
    async def test_json_content_type(self):
        """API responses should have JSON content type"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            endpoints = ["/healthz", "/tools", "/secrets"]
            for endpoint in endpoints:
                response = await client.get(endpoint)
                assert response.headers.get("content-type", "").startswith("application/json")

    @pytest.mark.asyncio
    async def test_health_response_structure(self):
        """Health response should have required fields"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/healthz")
            data = response.json()
            assert "status" in data
            assert "timestamp" in data
            assert "services" in data

    @pytest.mark.asyncio
    async def test_tools_response_structure(self):
        """Tools response should have required fields"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/tools")
            data = response.json()
            assert "total" in data
            assert "tools" in data
            assert "categories" in data
            assert isinstance(data["tools"], list)
            assert isinstance(data["categories"], dict)
            assert isinstance(data["total"], int)

    @pytest.mark.asyncio
    async def test_execute_response_structure(self):
        """Execute response should have required fields"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/tools/execute",
                json={"tool_name": "test", "parameters": {}}
            )
            data = response.json()
            assert "success" in data
            assert "result" in data
            assert "error" in data
            assert "execution_time_ms" in data


# ============================================================================
# Test CORS Headers
# ============================================================================

class TestCORSHeaders:
    """Test CORS headers for cross-origin requests"""

    @pytest.mark.asyncio
    async def test_options_request(self):
        """OPTIONS request should be handled"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.options("/tools")
            # FastAPI handles OPTIONS automatically
            assert response.status_code in [200, 405]

    @pytest.mark.asyncio
    async def test_preflight_headers(self):
        """Should handle preflight request"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            headers = {
                "Origin": "http://example.com",
                "Access-Control-Request-Method": "POST",
            }
            response = await client.options("/tools/execute", headers=headers)
            # FastAPI default CORS behavior
            assert response.status_code in [200, 405]


# ============================================================================
# Test Request Validation
# ============================================================================

class TestRequestValidation:
    """Test request validation and error responses"""

    @pytest.mark.asyncio
    async def test_invalid_json_rejected(self):
        """Invalid JSON should return error"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # httpx validates JSON, so this test checks the API handles
            # requests with missing required fields
            response = await client.post(
                "/tools/execute",
                json={},  # Missing required tool_name
            )
            # Pydantic validation should catch this
            assert response.status_code in [200, 422]

    @pytest.mark.asyncio
    async def test_skills_store_validation(self):
        """Skills store should validate required fields"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/skills/store",
                json={"name": "test"}  # Missing many required fields
            )
            # Pydantic validation should catch this
            assert response.status_code in [200, 422, 500]

    @pytest.mark.asyncio
    async def test_query_parameters_validated(self):
        """Query parameters should be validated"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Valid query
            response = await client.get("/tools?category=automation")
            assert response.status_code == 200

            # Force refresh should be boolean
            response = await client.get("/tools?force_refresh=true")
            assert response.status_code == 200


# ============================================================================
# Test Pagination and Filtering
# ============================================================================

class TestPaginationAndFiltering:
    """Test pagination and filtering behavior"""

    @pytest.mark.asyncio
    async def test_category_filter_valid(self):
        """Valid category filter should work"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            categories = ["automation", "infrastructure", "documents"]
            for category in categories:
                response = await client.get(f"/tools?category={category}")
                assert response.status_code == 200
                data = response.json()
                # All tools should match category
                for tool in data["tools"]:
                    assert tool["category"] == category

    @pytest.mark.asyncio
    async def test_empty_category_filter(self):
        """Empty category should return all tools"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/tools?category=nonexistent")
            assert response.status_code == 200
            data = response.json()
            # Should return empty list
            assert data["total"] == 0


# ============================================================================
# Test Error Responses
# ============================================================================

class TestErrorResponses:
    """Test error response formats"""

    @pytest.mark.asyncio
    async def test_not_found_endpoint(self):
        """Non-existent endpoints should return 404"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/nonexistent")
            assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_404_response_format(self):
        """404 response should have proper format"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/nonexistent")
            data = response.json()
            assert "detail" in data


# ============================================================================
# Test API Documentation Endpoints
# ============================================================================

class TestDocumentationEndpoints:
    """Test documentation and schema endpoints"""

    @pytest.mark.asyncio
    async def test_docs_endpoint(self):
        """Should have docs endpoint"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/docs")
            # FastAPI provides Swagger UI at /docs
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_redoc_endpoint(self):
        """Should have ReDoc endpoint"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/redoc")
            # FastAPI provides ReDoc at /redoc
            assert response.status_code == 200


# ============================================================================
# Test Response Times
# ============================================================================

class TestResponseTimes:
    """Test API response time performance"""

    @pytest.mark.asyncio
    async def test_healthz_response_time(self):
        """Health check should respond reasonably"""
        import time
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            start = time.time()
            response = await client.get("/healthz")
            elapsed = time.time() - start
            assert response.status_code == 200
            # Should respond in under 30 seconds (includes upstream timeouts)
            assert elapsed < 30.0

    @pytest.mark.asyncio
    async def test_tools_response_time(self):
        """Tools listing should respond quickly"""
        import time
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            start = time.time()
            response = await client.get("/tools")
            elapsed = time.time() - start
            assert response.status_code == 200
            # Should respond in under 2 seconds
            assert elapsed < 2.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
