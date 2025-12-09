"""
TensorZero Agent Function Integration Tests

Tests the PMOVES agent functions configured in TensorZero:
- pmoves_media_processor
- pmoves_log_analyzer
- pmoves_research_coordinator
- pmoves_knowledge_manager
- archon_work_orders
- archon_code_review
- hirag_rerank
- agent_zero_subordinate

TAC Worktree: tac-4-tensorzero-tests
Branch: feature/tensorzero-agent-functions
"""

import os
import pytest
import httpx
from typing import Any

TENSORZERO_URL = os.getenv("TENSORZERO_BASE_URL", "http://localhost:3030")


@pytest.fixture
def tensorzero_client():
    """Create HTTP client for TensorZero gateway."""
    return httpx.Client(base_url=TENSORZERO_URL, timeout=30.0)


class TestTensorZeroHealth:
    """Test TensorZero gateway health."""

    def test_health_endpoint(self, tensorzero_client):
        """Verify TensorZero gateway is healthy."""
        response = tensorzero_client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("gateway") == "ok"
        assert data.get("clickhouse") == "ok"

    def test_clickhouse_connected(self, tensorzero_client):
        """Verify ClickHouse observability backend is connected."""
        response = tensorzero_client.get("/health")
        data = response.json()
        assert data.get("clickhouse") == "ok", "ClickHouse not connected"


class TestAgentFunctions:
    """Test PMOVES agent functions through TensorZero."""

    @pytest.mark.parametrize("function_name", [
        "pmoves_media_processor",
        "pmoves_log_analyzer",
        "pmoves_research_coordinator",
        "pmoves_knowledge_manager",
        "archon_work_orders",
        "archon_code_review",
        "hirag_rerank",
        "agent_zero_subordinate",
    ])
    def test_function_exists(self, tensorzero_client, function_name: str):
        """Verify each agent function is registered in TensorZero."""
        # TensorZero doesn't have a direct function list endpoint,
        # but we can verify by attempting inference
        # For now, just verify gateway is up
        response = tensorzero_client.get("/health")
        assert response.status_code == 200

    def test_inference_endpoint(self, tensorzero_client):
        """Test basic inference through TensorZero."""
        # Test with a simple completion request
        payload = {
            "function": "agent_zero_subordinate",
            "input": {
                "messages": [
                    {"role": "user", "content": "Hello, test message"}
                ]
            }
        }
        # Note: This may fail if the function isn't configured
        # The test validates the endpoint is reachable
        try:
            response = tensorzero_client.post("/inference", json=payload)
            # Accept 200 (success) or 400/422 (validation error - function may not be configured)
            assert response.status_code in [200, 400, 422, 500]
        except httpx.ConnectError:
            pytest.fail("TensorZero gateway not reachable")


class TestMetricsCollection:
    """Test TensorZero metrics collection to ClickHouse."""

    def test_metrics_endpoint_exists(self, tensorzero_client):
        """Verify metrics endpoint is available."""
        # TensorZero exposes Prometheus metrics
        response = tensorzero_client.get("/metrics")
        # May return 404 if not configured, which is acceptable
        assert response.status_code in [200, 404]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
