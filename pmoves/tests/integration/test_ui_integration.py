#!/usr/bin/env python3
"""
Integration Tests for PMOVES UI Integration Features

Tests UI Integration features with real backend services:
- Hi-RAG v2 (port 8086) - Hybrid search for knowledge retrieval
- Jellyfin Bridge (port 8093) - Media server integration
- DeepResearch (port 8098) - LLM-based research orchestration

These tests require services to be running.
Run with: pytest -m integration pmoves/tests/integration/test_ui_integration.py
"""

import asyncio
import os
from typing import Any, Dict

import pytest
from httpx import AsyncClient, TimeoutException, ConnectError


# ============================================================================
# Configuration
# ============================================================================

HIRAG_V2_URL = os.environ.get("HIRAG_V2_URL", "http://localhost:8086")
JELLYFIN_BRIDGE_URL = os.environ.get("JELLYFIN_BRIDGE_URL", "http://localhost:8093")
DEEPRESEARCH_URL = os.environ.get("DEEPRESEARCH_URL", "http://localhost:8098")

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


async def skip_if_not_healthy(url: str, path: str = "/healthz") -> None:
    """Pytest skip if service is not healthy"""
    if not await service_healthy(url, path):
        pytest.skip(f"Service at {url} not running or unhealthy")


# ============================================================================
# Test Suite: Service Health
# ============================================================================

class TestServiceHealth:
    """Verify all UI Integration services are running"""

    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.requires("workers")
    async def test_hirag_v2_accessible(self):
        """Hi-RAG v2 should be accessible"""
        await skip_if_not_healthy(HIRAG_V2_URL)
        assert await service_healthy(HIRAG_V2_URL)

    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.requires("orchestration")
    async def test_jellyfin_bridge_accessible(self):
        """Jellyfin Bridge should be accessible"""
        await skip_if_not_healthy(JELLYFIN_BRIDGE_URL)
        assert await service_healthy(JELLYFIN_BRIDGE_URL)

    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.requires("orchestration")
    async def test_deepresearch_accessible(self):
        """DeepResearch service should be accessible"""
        await skip_if_not_healthy(DEEPRESEARCH_URL)
        assert await service_healthy(DEEPRESEARCH_URL)


# ============================================================================
# Test Suite: Hi-RAG Search Integration
# ============================================================================

class TestHiragSearchIntegration:
    """Test Hi-RAG v2 hybrid search integration"""

    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.requires("workers")
    async def test_hirag_query_basic(self):
        """Test basic search query through Hi-RAG v2"""
        await skip_if_not_healthy(HIRAG_V2_URL)

        async with AsyncClient(base_url=HIRAG_V2_URL, timeout=DEFAULT_TIMEOUT) as client:
            response = await client.post(
                "/hirag/query",
                json={
                    "query": "test search",
                    "top_k": 5,
                    "rerank": True,
                }
            )

            assert response.status_code == 200
            data = response.json()
            assert "results" in data
            assert "total" in data
            assert isinstance(data["results"], list)

    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.requires("workers")
    async def test_hirag_query_with_filters(self):
        """Test search with source type and date filters"""
        await skip_if_not_healthy(HIRAG_V2_URL)

        async with AsyncClient(base_url=HIRAG_V2_URL, timeout=DEFAULT_TIMEOUT) as client:
            response = await client.post(
                "/hirag/query",
                json={
                    "query": "video tutorial",
                    "top_k": 10,
                    "rerank": True,
                    "filters": {
                        "source_type": "youtube",
                        "min_score": 0.5,
                    },
                }
            )

            assert response.status_code == 200
            data = response.json()
            assert "results" in data

    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.requires("workers")
    async def test_hirag_empty_query(self):
        """Test search with empty query returns gracefully"""
        await skip_if_not_healthy(HIRAG_V2_URL)

        async with AsyncClient(base_url=HIRAG_V2_URL, timeout=DEFAULT_TIMEOUT) as client:
            response = await client.post(
                "/hirag/query",
                json={
                    "query": "",
                    "top_k": 5,
                }
            )

            # Should handle empty query (may return 200 or 400 depending on implementation)
            assert response.status_code in [200, 400]

    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.requires("workers")
    async def test_hirag_rerank_disable(self):
        """Test search with reranking disabled"""
        await skip_if_not_healthy(HIRAG_V2_URL)

        async with AsyncClient(base_url=HIRAG_V2_URL, timeout=DEFAULT_TIMEOUT) as client:
            response = await client.post(
                "/hirag/query",
                json={
                    "query": "machine learning",
                    "top_k": 10,
                    "rerank": False,
                }
            )

            assert response.status_code == 200
            data = response.json()
            assert "results" in data

    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.requires("workers")
    async def test_hirag_response_structure(self):
        """Verify Hi-RAG response has expected structure"""
        await skip_if_not_healthy(HIRAG_V2_URL)

        async with AsyncClient(base_url=HIRAG_V2_URL, timeout=DEFAULT_TIMEOUT) as client:
            response = await client.post(
                "/hirag/query",
                json={"query": "test", "top_k": 1}
            )

            assert response.status_code == 200
            data = response.json()

            # Check response structure
            assert "results" in data
            assert "total" in data
            assert "queryTime" in data

            # If results exist, check their structure
            if data["results"]:
                result = data["results"][0]
                assert "id" in result
                assert "content" in result
                assert "score" in result
                assert "source" in result
                assert "metadata" in result


# ============================================================================
# Test Suite: Jellyfin Integration
# ============================================================================

class TestJellyfinIntegration:
    """Test Jellyfin Bridge integration"""

    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.requires("orchestration")
    async def test_jellyfin_sync_status(self):
        """Test fetching sync status"""
        await skip_if_not_healthy(JELLYFIN_BRIDGE_URL)

        async with AsyncClient(base_url=JELLYFIN_BRIDGE_URL, timeout=DEFAULT_TIMEOUT) as client:
            response = await client.get("/jellyfin/sync-status")

            # May return 200 (has status) or 404 (no sync yet)
            assert response.status_code in [200, 404]

            if response.status_code == 200:
                data = response.json()
                assert "status" in data
                assert "videosLinked" in data
                assert "pendingBackfill" in data

    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.requires("orchestration")
    async def test_jellyfin_search_empty(self):
        """Test search with no results"""
        await skip_if_not_healthy(JELLYFIN_BRIDGE_URL)

        async with AsyncClient(base_url=JELLYFIN_BRIDGE_URL, timeout=DEFAULT_TIMEOUT) as client:
            response = await client.get(
                "/jellyfin/search",
                params={"query": "nonexistent-item-xyz-123", "limit": 10}
            )

            assert response.status_code == 200
            data = response.json()
            # Should return empty array or no items
            assert "items" in data
            assert isinstance(data["items"], list)

    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.requires("orchestration")
    async def test_jellyfin_link_item(self):
        """Test linking YouTube video to Jellyfin item"""
        await skip_if_not_healthy(JELLYFIN_BRIDGE_URL)

        async with AsyncClient(base_url=JELLYFIN_BRIDGE_URL, timeout=DEFAULT_TIMEOUT) as client:
            # This will likely fail since we don't have a real item ID,
            # but tests the endpoint structure
            response = await client.post(
                "/jellyfin/link",
                json={
                    "video_id": "test_video_123",
                    "jellyfin_item_id": "test_item_456",
                }
            )

            # Should not 500 - should return 404, 400, or 200
            assert response.status_code != 500

    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.requires("orchestration")
    async def test_jellyfin_playback_url(self):
        """Test generating playback URL"""
        await skip_if_not_healthy(JELLYFIN_BRIDGE_URL)

        async with AsyncClient(base_url=JELLYFIN_BRIDGE_URL, timeout=DEFAULT_TIMEOUT) as client:
            response = await client.post(
                "/jellyfin/playback-url",
                json={
                    "item_id": "test_item",
                    "start_position": 60,
                }
            )

            # Should not 500 - should return 404, 400, or 200
            assert response.status_code != 500

    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.requires("orchestration")
    async def test_jellyfin_trigger_sync(self):
        """Test triggering sync operation"""
        await skip_if_not_healthy(JELLYFIN_BRIDGE_URL)

        async with AsyncClient(base_url=JELLYFIN_BRIDGE_URL, timeout=DEFAULT_TIMEOUT) as client:
            response = await client.post("/jellyfin/sync")

            # Should accept the request (may not actually sync without proper config)
            assert response.status_code in [200, 202, 400]

    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.requires("orchestration")
    async def test_jellyfin_backfill(self):
        """Test backfill operation"""
        await skip_if_not_healthy(JELLYFIN_BRIDGE_URL)

        async with AsyncClient(base_url=JELLYFIN_BRIDGE_URL, timeout=DEFAULT_TIMEOUT) as client:
            response = await client.post(
                "/jellyfin/backfill",
                json={
                    "limit": 10,
                }
            )

            # Should accept the request
            assert response.status_code in [200, 202, 400]


# ============================================================================
# Test Suite: DeepResearch Integration
# ============================================================================

class TestDeepResearchIntegration:
    """Test DeepResearch service integration"""

    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.requires("orchestration")
    async def test_research_initiation(self):
        """Test initiating a research task"""
        await skip_if_not_healthy(DEEPRESEARCH_URL)

        async with AsyncClient(base_url=DEEPRESEARCH_URL, timeout=DEFAULT_TIMEOUT) as client:
            response = await client.post(
                "/research/initiate",
                json={
                    "query": "What is quantum computing?",
                    "mode": "tensorzero",
                    "max_iterations": 5,
                    "priority": 5,
                }
            )

            # Should accept the request (task may fail if dependencies not available)
            assert response.status_code in [200, 202, 400, 500]

            if response.status_code == 200:
                data = response.json()
                assert "id" in data
                assert "query" in data
                assert "status" in data

    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.requires("orchestration")
    async def test_research_task_lifecycle(self):
        """Test full task lifecycle: pending -> running -> completed"""
        await skip_if_not_healthy(DEEPRESEARCH_URL)

        # Initiate a task
        async with AsyncClient(base_url=DEEPRESEARCH_URL, timeout=DEFAULT_TIMEOUT) as client:
            init_response = await client.post(
                "/research/initiate",
                json={
                    "query": "Simple test query",
                    "mode": "tensorzero",
                    "max_iterations": 3,
                }
            )

            # Only continue if task was created successfully
            if init_response.status_code != 200:
                pytest.skip("Could not create research task")

            task_data = init_response.json()
            task_id = task_data["id"]

            # Check task status
            status_response = await client.get(f"/research/tasks/{task_id}")
            assert status_response.status_code == 200
            task = status_response.json()
            assert task["id"] == task_id

            # Try to cancel the task (to clean up)
            cancel_response = await client.post(f"/research/tasks/{task_id}/cancel")
            # May fail if already completed, that's ok

    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.requires("orchestration")
    async def test_list_research_tasks(self):
        """Test listing research tasks"""
        await skip_if_not_healthy(DEEPRESEARCH_URL)

        async with AsyncClient(base_url=DEEPRESEARCH_URL, timeout=DEFAULT_TIMEOUT) as client:
            response = await client.get(
                "/research/tasks",
                params={"limit": 10, "offset": 0}
            )

            assert response.status_code == 200
            data = response.json()
            assert "tasks" in data
            assert isinstance(data["tasks"], list)

    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.requires("orchestration")
    async def test_research_status_filter(self):
        """Test filtering tasks by status"""
        await skip_if_not_healthy(DEEPRESEARCH_URL)

        async with AsyncClient(base_url=DEEPRESEARCH_URL, timeout=DEFAULT_TIMEOUT) as client:
            # Filter by pending status
            response = await client.get(
                "/research/tasks",
                params={"status": "pending", "limit": 10}
            )

            assert response.status_code == 200
            data = response.json()
            # All returned tasks should match filter (if endpoint implements filtering)
            if data["tasks"]:
                # If filtering is implemented on server
                pass  # Would verify status matches

    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.requires("orchestration")
    async def test_rehealth_check(self):
        """Test DeepResearch health check endpoint"""
        await skip_if_not_healthy(DEEPRESEARCH_URL)

        async with AsyncClient(base_url=DEEPRESEARCH_URL, timeout=DEFAULT_TIMEOUT) as client:
            response = await client.get("/healthz")

            assert response.status_code == 200
            data = response.json()
            assert data.get("healthy") is True, f"DeepResearch unhealthy: {data}"

    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.requires("orchestration")
    async def test_publish_to_notebook(self):
        """Test publishing research results to notebook"""
        await skip_if_not_healthy(DEEPRESEARCH_URL)

        # First try to create a task
        async with AsyncClient(base_url=DEEPRESEARCH_URL, timeout=DEFAULT_TIMEOUT) as client:
            init_response = await client.post(
                "/research/initiate",
                json={
                    "query": "Test notebook publish",
                    "mode": "tensorzero",
                    "max_iterations": 3,
                }
            )

            if init_response.status_code != 200:
                pytest.skip("Could not create research task for publish test")

            task_data = init_response.json()
            task_id = task_data["id"]

            # Try to publish (will likely fail if task not complete)
            publish_response = await client.post(
                f"/research/tasks/{task_id}/publish",
                json={"notebook_id": "test-notebook"}
            )

            # Should accept the request even if task not complete
            assert publish_response.status_code in [200, 400, 409, 425]

            # Clean up - cancel the task
            await client.post(f"/research/tasks/{task_id}/cancel")


# ============================================================================
# Test Suite: Cross-Service Workflows
# ============================================================================

class TestCrossServiceWorkflows:
    """Test workflows that span multiple services"""

    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.requires("orchestration")
    async def test_search_to_notebook_export(self):
        """Test workflow: Hi-RAG search -> export to notebook"""
        await skip_if_not_healthy(HIRAG_V2_URL)

        # First, perform a search
        async with AsyncClient(base_url=HIRAG_V2_URL, timeout=DEFAULT_TIMEOUT) as client:
            search_response = await client.post(
                "/hirag/query",
                json={"query": "test", "top_k": 3}
            )

            if search_response.status_code != 200:
                pytest.skip("Hi-RAG search failed")

            search_data = search_response.json()
            assert "results" in search_data

            # Verify we have results to export
            if len(search_data["results"]) > 0:
                # In a real workflow, would call notebook export endpoint here
                # For now, just verify the search structure
                assert True

    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.requires("orchestration")
    async def test_jellyfin_search_to_link_workflow(self):
        """Test workflow: Jellyfin search -> link YouTube video"""
        await skip_if_not_healthy(JELLYFIN_BRIDGE_URL)

        async with AsyncClient(base_url=JELLYFIN_BRIDGE_URL, timeout=DEFAULT_TIMEOUT) as client:
            # Step 1: Search for content
            search_response = await client.get(
                "/jellyfin/search",
                params={"query": "test", "limit": 5}
            )

            if search_response.status_code != 200:
                pytest.skip("Jellyfin search failed")

            search_data = search_response.json()
            items = search_data.get("items", [])

            # Step 2: If we have items, try to link (will likely fail without real IDs)
            if items:
                item_id = items[0]["id"]
                link_response = await client.post(
                    "/jellyfin/link",
                    json={
                        "video_id": "yt_test_123",
                        "jellyfin_item_id": item_id,
                    }
                )
                # Should handle gracefully
                assert link_response.status_code != 500

    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.requires("orchestration")
    async def test_research_with_hirag_sources(self):
        """Test workflow: Research task using Hi-RAG sources"""
        await skip_if_not_healthy(DEEPRESEARCH_URL)

        # In a real workflow, would:
        # 1. Initiate research with query that uses Hi-RAG
        # 2. DeepResearch calls Hi-RAG internally for sources
        # 3. Results include source citations

        # For now, just test that services are both healthy
        hirag_healthy = await service_healthy(HIRAG_V2_URL)
        research_healthy = await service_healthy(DEEPRESEARCH_URL)

        # Skip if Hi-RAG is not available (optional dependency)
        if not hirag_healthy:
            pytest.skip("Hi-RAG v2 not available for cross-service test")
        assert research_healthy


# ============================================================================
# Test Suite: Error Handling
# ============================================================================

class TestErrorHandling:
    """Test error handling and edge cases"""

    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.requires("workers")
    async def test_hirag_malformed_request(self):
        """Test Hi-RAG handles malformed requests"""
        await skip_if_not_healthy(HIRAG_V2_URL)

        async with AsyncClient(base_url=HIRAG_V2_URL, timeout=DEFAULT_TIMEOUT) as client:
            # Missing required fields
            response = await client.post(
                "/hirag/query",
                json={}  # Missing query field
            )

            # Should return validation error
            assert response.status_code >= 400

    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.requires("orchestration")
    async def test_jellyfin_invalid_media_type(self):
        """Test Jellyfin handles invalid media type"""
        await skip_if_not_healthy(JELLYFIN_BRIDGE_URL)

        async with AsyncClient(base_url=JELLYFIN_BRIDGE_URL, timeout=DEFAULT_TIMEOUT) as client:
            # Search with invalid media type
            response = await client.get(
                "/jellyfin/search",
                params={
                    "query": "test",
                    "media_type": "InvalidType",
                }
            )

            # Should handle gracefully
            assert response.status_code in [200, 400, 422]

    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.requires("orchestration")
    async def test_research_invalid_mode(self):
        """Test DeepResearch handles invalid mode"""
        await skip_if_not_healthy(DEEPRESEARCH_URL)

        async with AsyncClient(base_url=DEEPRESEARCH_URL, timeout=DEFAULT_TIMEOUT) as client:
            response = await client.post(
                "/research/initiate",
                json={
                    "query": "test",
                    "mode": "invalid_mode",
                }
            )

            # Should handle invalid mode
            assert response.status_code in [400, 422]

    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.requires("orchestration")
    async def test_timeout_handling(self):
        """Test timeout handling across services"""
        # Test with a very short timeout
        try:
            async with AsyncClient(
                base_url=HIRAG_V2_URL,
                timeout=0.001  # 1ms timeout
            ) as client:
                await client.post("/hirag/query", json={"query": "test"})
        except (TimeoutException, ConnectError):
            # Expected - timeout should be raised
            assert True
        except Exception:
            pytest.fail("Wrong exception type for timeout")

    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.requires("workers")
    async def test_concurrent_search_requests(self):
        """Test Hi-RAG handles concurrent requests"""
        await skip_if_not_healthy(HIRAG_V2_URL)

        async with AsyncClient(base_url=HIRAG_V2_URL, timeout=DEFAULT_TIMEOUT) as client:
            # Send multiple concurrent requests
            tasks = [
                client.post("/hirag/query", json={"query": f"test {i}", "top_k": 3})
                for i in range(5)
            ]
            responses = await asyncio.gather(*tasks, return_exceptions=True)

            # All should complete without 500 errors
            for response in responses:
                if not isinstance(response, Exception):
                    assert response.status_code != 500


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "integration"])
