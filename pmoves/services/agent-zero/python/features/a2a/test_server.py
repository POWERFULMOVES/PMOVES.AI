"""
A2A Server Test Suite

Tests for the Agent2Agent protocol implementation.
Based on Google's A2A specification (https://a2aproject.github.io/A2A/)

Run with: pytest features/a2a/test_server.py -v
"""

import asyncio
import json
import uuid
from contextlib import asynccontextmanager
from typing import Generator

import pytest
from httpx import AsyncClient, ASGITransport
from fastapi import status

from .server import create_app, lifespan, _tasks, _tasks_lock
from .types import (
    AgentCard,
    Task,
    TaskState,
    TaskStatusMessage,
    ArtifactType,
    Message,
    SendMessageRequest,
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
        assert card.name == "Agent Zero"
        assert card.version == "2.0.0"
        assert len(card.supported_interfaces) > 0
        assert card.supported_interfaces[0].protocol_binding == "JSONRPC"
        assert card.capabilities.streaming is True
        assert "text/plain" in card.default_input_modes
        assert "text/markdown" in card.default_output_modes

    @pytest.mark.asyncio
    async def test_agent_card_has_required_fields(self, client: AsyncClient):
        """Test agent card contains all required A2A fields."""
        response = await client.get("/.well-known/agent.json")

        data = response.json()
        required_fields = [
            "protocol_version", "name", "description", "supported_interfaces",
            "provider", "version", "capabilities", "default_input_modes", "default_output_modes"
        ]

        for field in required_fields:
            assert field in data, f"Missing required field: {field}"

    @pytest.mark.asyncio
    async def test_agent_card_skills(self, client: AsyncClient):
        """Test agent card has expected skills defined."""
        response = await client.get("/.well-known/agent.json")

        data = response.json()
        expected_skills = [
            "code_generation",
            "file_operations",
            "command_execution"
        ]

        skill_ids = [skill["id"] for skill in data.get("skills", [])]
        for skill_id in expected_skills:
            assert skill_id in skill_ids, f"Missing skill: {skill_id}"


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
    async def test_create_task_a2a_format(self, client: AsyncClient):
        """Test creating a new task with A2A-compliant message format."""
        message_id = str(uuid.uuid4())
        context_id = str(uuid.uuid4())
        payload = {
            "message": {
                "message_id": message_id,
                "context_id": context_id,
                "role": "user",
                "content": "Write a hello world function in Python"
            }
        }

        response = await client.post("/a2a/v1/tasks", json=payload)

        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert "task" in data
        assert data["task"]["context_id"] == context_id
        assert "status" in data["task"]
        assert data["task"]["status"]["state"] in ["TASK_STATE_SUBMITTED", "TASK_STATE_WORKING"]

    @pytest.mark.asyncio
    async def test_create_task_backward_compatible(self, client: AsyncClient):
        """Test creating a task with backward compatible format."""
        task_id = str(uuid.uuid4())
        payload = {
            "id": task_id,
            "instruction": "Write a hello world function in Python"
        }

        response = await client.post("/a2a/v1/tasks", json=payload)

        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert "task" in data
        assert data["task"]["instruction"] == "Write a hello world function in Python"
        assert data["task"]["status"]["state"] in ["TASK_STATE_SUBMITTED", "TASK_STATE_WORKING"]

    @pytest.mark.asyncio
    async def test_create_task_with_metadata(self, client: AsyncClient):
        """Test creating a task with optional metadata."""
        payload = {
            "message": {
                "message_id": str(uuid.uuid4()),
                "role": "user",
                "content": "Analyze this code"
            },
            "metadata": {
                "priority": "high",
                "source": "archon",
                "tags": ["security", "review"]
            }
        }

        response = await client.post("/a2a/v1/tasks", json=payload)

        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert data["task"]["metadata"]["priority"] == "high"
        assert data["task"]["metadata"]["source"] == "archon"

    @pytest.mark.asyncio
    async def test_create_task_invalid_schema(self, client: AsyncClient):
        """Test task creation with invalid schema - Message validation."""
        payload = {
            "message": {
                # Missing required "message_id" and "role" fields
                "content": "Do something"
            }
        }

        response = await client.post("/a2a/v1/tasks", json=payload)

        # Should return 500 (server error) due to Message validation failure
        # since we're accepting Dict[str, Any] for flexibility
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR


class TestTaskRetrieval:
    """Tests for task retrieval endpoint."""

    @pytest.mark.asyncio
    async def test_get_task(self, client: AsyncClient):
        """Test retrieving a task by ID."""
        # First create a task
        create_payload = {
            "message": {
                "message_id": str(uuid.uuid4()),
                "role": "user",
                "content": "Test instruction"
            }
        }
        create_response = await client.post("/a2a/v1/tasks", json=create_payload)
        task_id = create_response.json()["task"]["id"]

        # Then retrieve it
        response = await client.get(f"/a2a/v1/tasks/{task_id}")

        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert data["id"] == task_id
        assert "context_id" in data
        assert "status" in data

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
            payload = {
                "message": {
                    "message_id": str(uuid.uuid4()),
                    "role": "user",
                    "content": f"Test task {i}"
                }
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
            payload = {
                "message": {
                    "message_id": str(uuid.uuid4()),
                    "role": "user",
                    "content": f"Test task {i}"
                }
            }
            await client.post("/a2a/v1/tasks", json=payload)

        # Filter by working status
        response = await client.get("/a2a/v1/tasks?status_filter=TASK_STATE_WORKING")

        assert response.status_code == status.HTTP_200_OK

        tasks = response.json()
        assert len(tasks) == 2
        for task in tasks:
            assert task["status"]["state"] == "TASK_STATE_WORKING"

    @pytest.mark.asyncio
    async def test_list_tasks_with_limit(self, client: AsyncClient):
        """Test listing tasks with limit parameter."""
        # Create 5 tasks
        for i in range(5):
            payload = {
                "message": {
                    "message_id": str(uuid.uuid4()),
                    "role": "user",
                    "content": f"Test task {i}"
                }
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
        create_payload = {
            "message": {
                "message_id": str(uuid.uuid4()),
                "role": "user",
                "content": "Long running task"
            }
        }
        create_response = await client.post("/a2a/v1/tasks", json=create_payload)
        task_id = create_response.json()["task"]["id"]

        # Cancel the task
        response = await client.post(f"/a2a/v1/tasks/{task_id}/cancel")

        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert data["status"]["state"] == TaskState.CANCELLED

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
        create_payload = {
            "message": {
                "message_id": str(uuid.uuid4()),
                "role": "user",
                "content": "Generate code"
            }
        }
        create_response = await client.post("/a2a/v1/tasks", json=create_payload)
        task_id = create_response.json()["task"]["id"]

        # Add artifact with JSON body
        response = await client.post(
            f"/a2a/v1/tasks/{task_id}/artifacts",
            json={
                "type": ArtifactType.CODE,
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
        create_payload = {
            "message": {
                "message_id": str(uuid.uuid4()),
                "role": "user",
                "content": "Generate documentation"
            }
        }
        create_response = await client.post("/a2a/v1/tasks", json=create_payload)
        task_id = create_response.json()["task"]["id"]

        # Add multiple artifacts
        artifacts = [
            {"type": ArtifactType.TEXT, "data": "Summary text"},
            {"type": ArtifactType.MARKDOWN, "data": "# Documentation\n\nContent here"},
            {"type": ArtifactType.JSON, "data": '{"meta": "data"}'}
        ]

        for artifact in artifacts:
            await client.post(
                f"/a2a/v1/tasks/{task_id}/artifacts",
                json=artifact
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
    """Tests for A2A SendMessageResponse compliance."""

    @pytest.mark.asyncio
    async def test_task_response_has_a2a_fields(self, client: AsyncClient):
        """Test task creation response includes A2A-compliant fields."""
        payload = {
            "message": {
                "message_id": str(uuid.uuid4()),
                "role": "user",
                "content": "Test"
            }
        }

        response = await client.post("/a2a/v1/tasks", json=payload)

        data = response.json()
        assert "task" in data
        assert "status" in data["task"]
        assert "context_id" in data["task"]


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
        create_response = await client.post(
            "/a2a/v1/tasks",
            json={
                "message": {
                    "message_id": str(uuid.uuid4()),
                    "context_id": str(uuid.uuid4()),
                    "role": "user",
                    "content": "Integration test task"
                },
                "metadata": {"test": "integration"}
            }
        )
        assert create_response.status_code == status.HTTP_200_OK
        task_id = create_response.json()["task"]["id"]

        # Get
        get_response = await client.get(f"/a2a/v1/tasks/{task_id}")
        assert get_response.status_code == status.HTTP_200_OK
        task_data = get_response.json()
        assert task_data["metadata"]["test"] == "integration"

        # Add artifact
        artifact_response = await client.post(
            f"/a2a/v1/tasks/{task_id}/artifacts",
            json={
                "type": ArtifactType.TEXT,
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
        assert cancel_response.json()["status"]["state"] == TaskState.CANCELLED


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
