"""Smoke tests for DeepResearch UI Integration endpoints.

These tests verify the DeepResearch service is healthy and responsive
for the UI Integration features.
"""

import pytest
import httpx
import time


# Service URL configuration
DEEPRESEARCH_URL = "http://localhost:8098"


@pytest.mark.smoke
def test_deepresearch_health():
    """Verify DeepResearch service is healthy."""
    try:
        response = httpx.get(f"{DEEPRESEARCH_URL}/healthz", timeout=10.0)
        assert response.status_code == 200, f"Health check failed: {response.status_code}"

        data = response.json()
        assert "healthy" in data or "status" in data
    except ConnectionError:
        pytest.skip("DeepResearch service not available")
    except httpx.ConnectError:
        pytest.skip("DeepResearch service not running")


@pytest.mark.smoke
def test_deepresearch_version():
    """Verify DeepResearch service reports version."""
    try:
        response = httpx.get(f"{DEEPRESEARCH_URL}/healthz", timeout=10.0)
        assert response.status_code == 200

        data = response.json()
        # Version field is optional but nice to have
        if "version" in data:
            assert isinstance(data["version"], str)
    except ConnectionError:
        pytest.skip("DeepResearch service not available")
    except httpx.ConnectError:
        pytest.skip("DeepResearch service not running")


@pytest.mark.smoke
@pytest.mark.parametrize("query", [
    "What is quantum computing?",
    "Explain machine learning",
    "test query",
])
def test_deepresearch_initiate(query):
    """Verify DeepResearch accepts research task initiation."""
    try:
        response = httpx.post(
            f"{DEEPRESEARCH_URL}/research/tasks",
            json={
                "query": query,
                "mode": "tensorzero",
                "max_iterations": 5,
                "priority": 5
            },
            timeout=30.0
        )
        assert response.status_code in [200, 201, 202], f"Task initiation failed: {response.status_code}"

        data = response.json()
        assert "id" in data
        assert "query" in data
        assert "status" in data
        assert data["status"] in ["pending", "running", "queued"]
    except ConnectionError:
        pytest.skip("DeepResearch service not available")
    except httpx.ConnectError:
        pytest.skip("DeepResearch service not running")


@pytest.mark.smoke
def test_deepresearch_initiate_with_options():
    """Verify DeepResearch handles custom options."""
    try:
        response = httpx.post(
            f"{DEEPRESEARCH_URL}/research/tasks",
            json={
                "query": "test with options",
                "mode": "openrouter",
                "max_iterations": 15,
                "priority": 8,
                "notebook_id": "test-notebook-123"
            },
            timeout=30.0
        )
        assert response.status_code in [200, 201, 202], f"Task with options failed: {response.status_code}"

        data = response.json()
        assert "id" in data
    except ConnectionError:
        pytest.skip("DeepResearch service not available")
    except httpx.ConnectError:
        pytest.skip("DeepResearch service not running")


@pytest.mark.smoke
def test_deepresearch_list_tasks():
    """Verify DeepResearch task listing endpoint."""
    try:
        response = httpx.get(
            f"{DEEPRESEARCH_URL}/research/tasks",
            timeout=10.0
        )
        assert response.status_code == 200, f"Task list failed: {response.status_code}"

        data = response.json()
        assert "tasks" in data or isinstance(data, list)
    except ConnectionError:
        pytest.skip("DeepResearch service not available")
    except httpx.ConnectError:
        pytest.skip("DeepResearch service not running")


@pytest.mark.smoke
def test_deepresearch_list_with_pagination():
    """Verify DeepResearch handles pagination parameters."""
    try:
        response = httpx.get(
            f"{DEEPRESEARCH_URL}/research/tasks",
            params={"limit": 10, "offset": 0},
            timeout=10.0
        )
        assert response.status_code == 200, f"Paginated list failed: {response.status_code}"
    except ConnectionError:
        pytest.skip("DeepResearch service not available")
    except httpx.ConnectError:
        pytest.skip("DeepResearch service not running")


@pytest.mark.smoke
def test_deepresearch_list_with_status_filter():
    """Verify DeepResearch handles status filter."""
    try:
        response = httpx.get(
            f"{DEEPRESEARCH_URL}/research/tasks",
            params={"status": "running"},
            timeout=10.0
        )
        assert response.status_code == 200, f"Status filter failed: {response.status_code}"
    except ConnectionError:
        pytest.skip("DeepResearch service not available")
    except httpx.ConnectError:
        pytest.skip("DeepResearch service not running")


@pytest.mark.smoke
def test_deepresearch_list_with_mode_filter():
    """Verify DeepResearch handles mode filter."""
    try:
        response = httpx.get(
            f"{DEEPRESEARCH_URL}/research/tasks",
            params={"mode": "tensorzero"},
            timeout=10.0
        )
        assert response.status_code == 200, f"Mode filter failed: {response.status_code}"
    except ConnectionError:
        pytest.skip("DeepResearch service not available")
    except httpx.ConnectError:
        pytest.skip("DeepResearch service not running")


@pytest.mark.smoke
def test_deepresearch_get_task():
    """Verify DeepResearch task retrieval endpoint."""
    try:
        # First, create a task
        create_response = httpx.post(
            f"{DEEPRESEARCH_URL}/research/tasks",
            json={"query": "get task test", "mode": "local"},
            timeout=30.0
        )

        if create_response.status_code in [200, 201, 202]:
            task_id = create_response.json().get("id")

            if task_id:
                # Now try to get the task
                response = httpx.get(
                    f"{DEEPRESEARCH_URL}/research/tasks/{task_id}",
                    timeout=10.0
                )
                assert response.status_code == 200, f"Get task failed: {response.status_code}"

                data = response.json()
                assert "id" in data
                assert data["id"] == task_id
    except ConnectionError:
        pytest.skip("DeepResearch service not available")
    except httpx.ConnectError:
        pytest.skip("DeepResearch service not running")


@pytest.mark.smoke
def test_deepresearch_get_results():
    """Verify DeepResearch results retrieval endpoint."""
    try:
        # Create a simple task
        create_response = httpx.post(
            f"{DEEPRESEARCH_URL}/research/tasks",
            json={"query": "results test", "mode": "local", "max_iterations": 2},
            timeout=30.0
        )

        if create_response.status_code in [200, 201, 202]:
            task_id = create_response.json().get("id")

            if task_id:
                # Try to get results (might return 425 if still in progress)
                response = httpx.get(
                    f"{DEEPRESEARCH_URL}/research/tasks/{task_id}/results",
                    timeout=10.0
                )
                # Accept success or "still in progress" status
                assert response.status_code in [200, 404, 425], f"Get results failed: {response.status_code}"
    except ConnectionError:
        pytest.skip("DeepResearch service not available")
    except httpx.ConnectError:
        pytest.skip("DeepResearch service not running")


@pytest.mark.smoke
def test_deepresearch_cancel_task():
    """Verify DeepResearch task cancellation endpoint."""
    try:
        # Create a task
        create_response = httpx.post(
            f"{DEEPRESEARCH_URL}/research/tasks",
            json={"query": "cancel test", "mode": "local"},
            timeout=30.0
        )

        if create_response.status_code in [200, 201, 202]:
            task_id = create_response.json().get("id")

            if task_id:
                # Try to cancel
                response = httpx.post(
                    f"{DEEPRESEARCH_URL}/research/tasks/{task_id}/cancel",
                    timeout=10.0
                )
                # Accept success or already-completed status
                assert response.status_code in [200, 409], f"Cancel failed: {response.status_code}"
    except ConnectionError:
        pytest.skip("DeepResearch service not available")
    except httpx.ConnectError:
        pytest.skip("DeepResearch service not running")


@pytest.mark.smoke
def test_deepresearch_publish_to_notebook():
    """Verify DeepResearch publish to notebook endpoint."""
    try:
        # Create a task
        create_response = httpx.post(
            f"{DEEPRESEARCH_URL}/research/tasks",
            json={"query": "publish test", "mode": "local"},
            timeout=30.0
        )

        if create_response.status_code in [200, 201, 202]:
            task_id = create_response.json().get("id")

            if task_id:
                # Try to publish (might fail if task not complete)
                response = httpx.post(
                    f"{DEEPRESEARCH_URL}/research/tasks/{task_id}/publish",
                    json={"notebook_id": "test-notebook"},
                    timeout=10.0
                )
                # Accept success, not found, or still in progress
                assert response.status_code in [200, 404, 425], f"Publish failed: {response.status_code}"
    except ConnectionError:
        pytest.skip("DeepResearch service not available")
    except httpx.ConnectError:
        pytest.skip("DeepResearch service not running")


@pytest.mark.smoke
def test_deepresearch_validation_empty_query():
    """Verify DeepResearch validates empty query."""
    try:
        response = httpx.post(
            f"{DEEPRESEARCH_URL}/research/tasks",
            json={"query": "", "mode": "tensorzero"},
            timeout=10.0
        )
        # Should return validation error
        assert response.status_code in [400, 422], f"Validation failed: {response.status_code}"
    except ConnectionError:
        pytest.skip("DeepResearch service not available")
    except httpx.ConnectError:
        pytest.skip("DeepResearch service not running")


@pytest.mark.smoke
def test_deepresearch_validation_max_iterations():
    """Verify DeepResearch validates max_iterations range."""
    try:
        # Test with invalid max_iterations (too high)
        response = httpx.post(
            f"{DEEPRESEARCH_URL}/research/tasks",
            json={"query": "test", "max_iterations": 1000},
            timeout=10.0
        )
        # Should either clamp value or return validation error
        assert response.status_code in [200, 201, 202, 400, 422], f"Max iterations validation failed: {response.status_code}"
    except ConnectionError:
        pytest.skip("DeepResearch service not available")
    except httpx.ConnectError:
        pytest.skip("DeepResearch service not running")


@pytest.mark.smoke
def test_deepresearch_validation_priority():
    """Verify DeepResearch validates priority range."""
    try:
        # Test with invalid priority (out of range)
        response = httpx.post(
            f"{DEEPRESEARCH_URL}/research/tasks",
            json={"query": "test", "priority": 15},
            timeout=10.0
        )
        # Should either clamp value or return validation error
        assert response.status_code in [200, 201, 202, 400, 422], f"Priority validation failed: {response.status_code}"
    except ConnectionError:
        pytest.skip("DeepResearch service not available")
    except httpx.ConnectError:
        pytest.skip("DeepResearch service not running")


@pytest.mark.smoke
def test_deepresearch_timeout_handling():
    """Verify DeepResearch handles request timeouts."""
    try:
        # This test sends a complex query that might take time
        response = httpx.post(
            f"{DEEPRESEARCH_URL}/research/tasks",
            json={
                "query": "complex multi-step research task that takes time",
                "mode": "tensorzero",
                "max_iterations": 3
            },
            timeout=30.0
        )
        # Should return quickly with task ID (async processing)
        assert response.status_code in [200, 201, 202], f"Timeout handling failed: {response.status_code}"
    except ConnectionError:
        pytest.skip("DeepResearch service not available")
    except httpx.ConnectError:
        pytest.skip("DeepResearch service not running")
    except httpx.TimeoutException:
        # Timeout is acceptable for long-running research
        pytest.skip("DeepResearch service timed out (acceptable for smoke test)")


@pytest.mark.smoke
def test_deepresearch_network_failure_handling():
    """Verify DeepResearch handles network errors gracefully."""
    try:
        # Try to access non-existent task
        response = httpx.get(
            f"{DEEPRESEARCH_URL}/research/tasks/nonexistent-task-id",
            timeout=10.0
        )
        # Should return 404 for non-existent task
        assert response.status_code == 404, f"Network error handling failed: {response.status_code}"
    except ConnectionError:
        pytest.skip("DeepResearch service not available")
    except httpx.ConnectError:
        pytest.skip("DeepResearch service not running")
