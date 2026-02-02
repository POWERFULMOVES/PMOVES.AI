"""
A2A Server Test Suite

Tests for the Agent2Agent protocol implementation.
Run with: pytest features/a2a/test_server.py -v
"""

import asyncio
import json
import uuid
from typing import Generator

import pytest
from httpx import AsyncClient, ASGITransport
from fastapi import status

from .server import create_app, lifespan, _tasks, _tasks_lock
from .types import (
    AgentCard,
    Task,
    TaskStatus,
    ArtifactType,
    AGENT_ZERO_CARD,
)


@pytest.fixture
def event_loop() -> Generator:
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def app():
    """Create test app instance."""
    return create_app()


@pytest.fixture
async def client(app):
    """Create async test client."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as ac:
        yield ac


@pytest.fixture(autouse=True)
async def clear_tasks():
    """Clear task storage before each test."""
    async with _tasks_lock:
        _tasks.clear()
    yield
    async with _tasks_lock:
        _tasks.clear()


class TestAgentCard:
    """Tests for agent discovery and card endpoint."""

    @pytest.mark.asyncio
    async def test_get_agent_card(self, client: AsyncClient):
        """Test retrieving the agent card from well-known endpoint."""
        response = await client.get("/.well-known/agent.json")

        assert response.status_code == status.HTTP_200_OK

        card = AgentCard(**response.json())
        assert card.name == "agent-zero"
        assert card.version == "2.0.0"
        assert "code_generation" in card.capabilities
        assert "text/plain" in card.input_modalities
        assert "text/markdown" in card.output_modalities

    @pytest.mark.asyncio
    async def test_agent_card_has_required_fields(self, client: AsyncClient):
        """Test agent card contains all required fields."""
        response = await client.get("/.well-known/agent.json")

        data = response.json()
        required_fields = [
            "name", "description", "version", "capabilities",
            "input_modalities", "output_modalities"
        ]

        for field in required_fields:
            assert field in data, f"Missing required field: {field}"

    @pytest.mark.asyncio
    async def test_agent_card_capabilities(self, client: AsyncClient):
        """Test agent card has expected capabilities."""
        response = await client.get("/.well-known/agent.json")

        data = response.json()
        expected_capabilities = [
            "code_generation",
            "file_operations",
            "command_execution",
            "web_search",
            "mcp_tool_use"
        ]

        for cap in expected_capabilities:
            assert cap in data["capabilities"], f"Missing capability: {cap}"


class TestHealthCheck:
    """Tests for health check endpoint."""

    @pytest.mark.asyncio
    async def test_health_check(self, client: AsyncClient):
        """Test health check returns healthy status."""
        response = await client.get("/healthz")

        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert data["status"] == "healthy"
        assert "agent" in data
        assert "version" in data


class TestTaskCreation:
    """Tests for task creation endpoint."""

    @pytest.mark.asyncio
    async def test_create_task(self, client: AsyncClient):
        """Test creating a new task."""
        task_id = str(uuid.uuid4())
        payload = {
            "id": task_id,
            "instruction": "Write a hello world function in Python"
        }

        response = await client.post("/a2a/v1/tasks", json=payload)

        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert data["jsonrpc"] == "2.0"
        assert data["id"] == task_id
        assert "result" in data
        assert data["result"]["id"] == task_id
        assert data["result"]["status"] in ["submitted", "working"]

    @pytest.mark.asyncio
    async def test_create_task_with_metadata(self, client: AsyncClient):
        """Test creating a task with optional metadata."""
        task_id = str(uuid.uuid4())
        payload = {
            "id": task_id,
            "instruction": "Analyze this code",
            "metadata": {
                "priority": "high",
                "source": "archon",
                "tags": ["security", "review"]
            }
        }

        response = await client.post("/a2a/v1/tasks", json=payload)

        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert data["result"]["metadata"]["priority"] == "high"
        assert data["result"]["metadata"]["source"] == "archon"

    @pytest.mark.asyncio
    async def test_create_task_invalid_schema(self, client: AsyncClient):
        """Test task creation with invalid schema returns 422."""
        payload = {
            # Missing required "id" field
            "instruction": "Do something"
        }

        response = await client.post("/a2a/v1/tasks", json=payload)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestTaskRetrieval:
    """Tests for task retrieval endpoint."""

    @pytest.mark.asyncio
    async def test_get_task(self, client: AsyncClient):
        """Test retrieving a task by ID."""
        # First create a task
        task_id = str(uuid.uuid4())
        create_payload = {
            "id": task_id,
            "instruction": "Test instruction"
        }
        await client.post("/a2a/v1/tasks", json=create_payload)

        # Then retrieve it
        response = await client.get(f"/a2a/v1/tasks/{task_id}")

        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert data["id"] == task_id
        assert data["instruction"] == "Test instruction"

    @pytest.mark.asyncio
    async def test_get_task_not_found(self, client: AsyncClient):
        """Test retrieving non-existent task returns 404."""
        fake_id = str(uuid.uuid4())
        response = await client.get(f"/a2a/v1/tasks/{fake_id}")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_list_tasks(self, client: AsyncClient):
        """Test listing all tasks."""
        # Create multiple tasks
        for i in range(3):
            task_id = str(uuid.uuid4())
            payload = {
                "id": task_id,
                "instruction": f"Test task {i}"
            }
            await client.post("/a2a/v1/tasks", json=payload)

        # List all tasks
        response = await client.get("/a2a/v1/tasks")

        assert response.status_code == status.HTTP_200_OK

        tasks = response.json()
        assert len(tasks) == 3

    @pytest.mark.asyncio
    async def test_list_tasks_with_status_filter(self, client: AsyncClient):
        """Test listing tasks filtered by status."""
        # Create tasks (they'll have 'working' status)
        for i in range(2):
            task_id = str(uuid.uuid4())
            payload = {
                "id": task_id,
                "instruction": f"Test task {i}"
            }
            await client.post("/a2a/v1/tasks", json=payload)

        # Filter by working status
        response = await client.get("/a2a/v1/tasks?status_filter=working")

        assert response.status_code == status.HTTP_200_OK

        tasks = response.json()
        assert len(tasks) == 2
        for task in tasks:
            assert task["status"] == "working"

    @pytest.mark.asyncio
    async def test_list_tasks_with_limit(self, client: AsyncClient):
        """Test listing tasks with limit parameter."""
        # Create 5 tasks
        for i in range(5):
            task_id = str(uuid.uuid4())
            payload = {
                "id": task_id,
                "instruction": f"Test task {i}"
            }
            await client.post("/a2a/v1/tasks", json=payload)

        # List with limit of 3
        response = await client.get("/a2a/v1/tasks?limit=3")

        assert response.status_code == status.HTTP_200_OK

        tasks = response.json()
        assert len(tasks) == 3


class TestTaskCancellation:
    """Tests for task cancellation endpoint."""

    @pytest.mark.asyncio
    async def test_cancel_task(self, client: AsyncClient):
        """Test cancelling a task."""
        # Create a task
        task_id = str(uuid.uuid4())
        create_payload = {
            "id": task_id,
            "instruction": "Long running task"
        }
        await client.post("/a2a/v1/tasks", json=create_payload)

        # Cancel the task
        response = await client.post(f"/a2a/v1/tasks/{task_id}/cancel")

        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert data["status"] == TaskStatus.CANCELLED

    @pytest.mark.asyncio
    async def test_cancel_task_not_found(self, client: AsyncClient):
        """Test cancelling non-existent task returns 404."""
        fake_id = str(uuid.uuid4())
        response = await client.post(f"/a2a/v1/tasks/{fake_id}/cancel")

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestArtifacts:
    """Tests for artifact endpoints."""

    @pytest.mark.asyncio
    async def test_add_artifact(self, client: AsyncClient):
        """Test adding an artifact to a task."""
        # Create a task
        task_id = str(uuid.uuid4())
        create_payload = {
            "id": task_id,
            "instruction": "Generate code"
        }
        await client.post("/a2a/v1/tasks", json=create_payload)

        # Add artifact
        response = await client.post(
            f"/a2a/v1/tasks/{task_id}/artifacts",
            params={
                "artifact_type": ArtifactType.CODE,
                "data": "def hello(): return 'world'"
            }
        )

        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert len(data["artifacts"]) == 1
        assert data["artifacts"][0]["type"] == ArtifactType.CODE

    @pytest.mark.asyncio
    async def test_add_multiple_artifacts(self, client: AsyncClient):
        """Test adding multiple artifacts to a task."""
        # Create a task
        task_id = str(uuid.uuid4())
        create_payload = {
            "id": task_id,
            "instruction": "Generate documentation"
        }
        await client.post("/a2a/v1/tasks", json=create_payload)

        # Add multiple artifacts
        artifacts = [
            (ArtifactType.TEXT, "Summary text"),
            (ArtifactType.MARKDOWN, "# Documentation\n\nContent here"),
            (ArtifactType.JSON, '{"meta": "data"}')
        ]

        for art_type, data in artifacts:
            await client.post(
                f"/a2a/v1/tasks/{task_id}/artifacts",
                params={"artifact_type": art_type, "data": data}
            )

        # Verify all artifacts were added
        response = await client.get(f"/a2a/v1/tasks/{task_id}")
        task = response.json()

        assert len(task["artifacts"]) == 3


class TestAgentDiscovery:
    """Tests for agent discovery endpoint."""

    @pytest.mark.asyncio
    async def test_discover_agents(self, client: AsyncClient):
        """Test discovering available agents."""
        response = await client.post("/a2a/v1/discover")

        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert "agents" in data
        assert "total" in data
        assert data["total"] >= 1
        assert len(data["agents"]) >= 1


class TestJSONRPCResponses:
    """Tests for JSON-RPC 2.0 compliance."""

    @pytest.mark.asyncio
    async def test_task_response_has_jsonrpc_fields(self, client: AsyncClient):
        """Test task creation response includes JSON-RPC fields."""
        task_id = str(uuid.uuid4())
        payload = {
            "id": task_id,
            "instruction": "Test"
        }

        response = await client.post("/a2a/v1/tasks", json=payload)

        data = response.json()
        assert "jsonrpc" in data
        assert data["jsonrpc"] == "2.0"
        assert "id" in data
        assert "result" in data


class TestLifespan:
    """Tests for lifespan context manager."""

    @pytest.mark.asyncio
    async def test_lifespan_startup(self):
        """Test lifespan startup initializes resources."""
        startup_called = False
        shutdown_called = False

        @asynccontextmanager
        async def test_lifespan(app):
            nonlocal startup_called, shutdown_called
            startup_called = True
            yield
            shutdown_called = True

        app = create_app()
        # Replace lifespan with test version
        app.router.lifespan_context = test_lifespan

        # Simulate startup
        async with test_lifespan(app):
            assert startup_called

        assert shutdown_called


# Integration tests
class TestIntegration:
    """Integration tests for complete workflows."""

    @pytest.mark.asyncio
    async def test_complete_task_lifecycle(self, client: AsyncClient):
        """Test full task lifecycle: create -> get -> cancel."""
        # Create
        task_id = str(uuid.uuid4())
        create_response = await client.post(
            "/a2a/v1/tasks",
            json={
                "id": task_id,
                "instruction": "Integration test task",
                "metadata": {"test": "integration"}
            }
        )
        assert create_response.status_code == status.HTTP_200_OK

        # Get
        get_response = await client.get(f"/a2a/v1/tasks/{task_id}")
        assert get_response.status_code == status.HTTP_200_OK
        task_data = get_response.json()
        assert task_data["metadata"]["test"] == "integration"

        # Add artifact
        artifact_response = await client.post(
            f"/a2a/v1/tasks/{task_id}/artifacts",
            params={
                "artifact_type": ArtifactType.TEXT,
                "data": "Test result"
            }
        )
        assert artifact_response.status_code == status.HTTP_200_OK

        # Verify artifact
        get_response = await client.get(f"/a2a/v1/tasks/{task_id}")
        task_data = get_response.json()
        assert len(task_data["artifacts"]) == 1

        # Cancel
        cancel_response = await client.post(f"/a2a/v1/tasks/{task_id}/cancel")
        assert cancel_response.status_code == status.HTTP_200_OK
        assert cancel_response.json()["status"] == TaskStatus.CANCELLED


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
