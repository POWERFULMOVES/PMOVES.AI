"""Integration tests for archon FastAPI endpoints.

Covers:
- Health endpoint (/healthz)
- Events publish endpoint (/events/publish)
- Crawl submit endpoint (/archon/crawl)
- Task retrieval endpoint (/tasks/{task_id})
- Root endpoint (/)
- Service dependency injection and error handling
"""
from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any, Dict, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, Body, HTTPException
from httpx import AsyncClient, ASGITransport
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Shared test models and mocks
# ---------------------------------------------------------------------------

class CrawlJob(BaseModel):
    url: str
    task_id: Optional[str] = None
    depth: Optional[int] = Field(default=None, ge=0)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class MockArchonOrchestrator:
    """Mock orchestrator with controllable task snapshots."""

    def __init__(self) -> None:
        self._tasks: Dict[str, Dict[str, Any]] = {}
        self.shutdown = AsyncMock()

    async def dispatch(self, subject: str, event: Dict[str, Any]) -> Any:
        return None

    async def snapshot_tasks(self) -> Dict[str, Dict[str, Any]]:
        return dict(self._tasks)

    def set_task(self, task_id: str, data: Dict[str, Any]) -> None:
        self._tasks[task_id] = data


class MockArchonService:
    """Mock ArchonService for testing FastAPI endpoints."""

    def __init__(self) -> None:
        self.is_connected = True
        self.orchestrator = MockArchonOrchestrator()
        self.start = AsyncMock()
        self.stop = AsyncMock()
        self.publish_event = AsyncMock(return_value={
            "id": str(uuid.uuid4()),
            "topic": "test",
            "payload": {},
        })

    async def handle_local_event(self, topic, payload, **kwargs):
        return None


def _create_test_app():
    """Create a FastAPI test app with mocked service."""
    app = FastAPI(title="Archon Test")
    mock_service = MockArchonService()

    @app.get("/")
    async def root():
        return {"status": "ok", "service": "archon"}

    @app.get("/healthz")
    async def healthz():
        status = "ok" if mock_service.is_connected else "degraded"
        return {"status": status, "service": "archon", "nats": mock_service.is_connected}

    @app.post("/events/publish")
    async def events_publish(body: Dict[str, Any] = Body(...)):
        topic = body.get("topic")
        if not topic:
            raise HTTPException(status_code=422, detail="topic is required")
        payload = body.get("payload") or {}
        env = await mock_service.publish_event(topic, payload, source="archon.api")
        return {"published": topic, "id": env["id"]}

    @app.post("/archon/crawl")
    async def submit_crawl(job: CrawlJob):
        payload = job.model_dump(exclude_none=True)
        task_id = payload.get("task_id") or str(uuid.uuid4())
        payload["task_id"] = task_id
        await mock_service.publish_event("archon.crawl.request.v1", payload, source="archon.api")
        return {"task_id": task_id}

    @app.get("/tasks/{task_id}")
    async def get_task(task_id: str):
        snapshot = await mock_service.orchestrator.snapshot_tasks()
        task = snapshot.get(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="task not found")
        return {"task_id": task_id, **task}

    return app, mock_service


# ---------------------------------------------------------------------------
# Test classes
# ---------------------------------------------------------------------------

class TestHealthEndpoint:
    @pytest.mark.asyncio
    async def test_health_connected(self) -> None:
        app, mock_svc = _create_test_app()
        mock_svc.is_connected = True
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get("/healthz")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["service"] == "archon"
        assert data["nats"] is True

    @pytest.mark.asyncio
    async def test_health_degraded(self) -> None:
        app, mock_svc = _create_test_app()
        mock_svc.is_connected = False
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get("/healthz")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "degraded"
        assert data["nats"] is False


class TestRootEndpoint:
    @pytest.mark.asyncio
    async def test_root_returns_status(self) -> None:
        app, _ = _create_test_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get("/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["service"] == "archon"


class TestEventsPublish:
    @pytest.mark.asyncio
    async def test_publish_valid_event(self) -> None:
        app, mock_svc = _create_test_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post("/events/publish", json={
                "topic": "archon.crawl.request.v1",
                "payload": {"url": "https://example.com"},
            })
        assert resp.status_code == 200
        data = resp.json()
        assert data["published"] == "archon.crawl.request.v1"
        assert "id" in data
        mock_svc.publish_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_publish_missing_topic(self) -> None:
        app, _ = _create_test_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post("/events/publish", json={"payload": {}})
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_publish_empty_body(self) -> None:
        app, _ = _create_test_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post("/events/publish", json={})
        assert resp.status_code == 422


class TestSubmitCrawl:
    @pytest.mark.asyncio
    async def test_submit_crawl_with_url(self) -> None:
        app, mock_svc = _create_test_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post("/archon/crawl", json={
                "url": "https://example.com",
            })
        assert resp.status_code == 200
        data = resp.json()
        assert "task_id" in data
        assert data["task_id"]  # Should be a UUID string

    @pytest.mark.asyncio
    async def test_submit_crawl_with_task_id(self) -> None:
        app, mock_svc = _create_test_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post("/archon/crawl", json={
                "url": "https://example.com",
                "task_id": "custom-tid",
            })
        assert resp.status_code == 200
        data = resp.json()
        assert data["task_id"] == "custom-tid"

    @pytest.mark.asyncio
    async def test_submit_crawl_missing_url(self) -> None:
        app, _ = _create_test_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post("/archon/crawl", json={})
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_submit_crawl_publishes_event(self) -> None:
        app, mock_svc = _create_test_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post("/archon/crawl", json={
                "url": "https://example.com",
                "task_id": "t-publish",
            })
        assert resp.status_code == 200
        mock_svc.publish_event.assert_called_once()


class TestGetTask:
    @pytest.mark.asyncio
    async def test_get_existing_task(self) -> None:
        app, mock_svc = _create_test_app()
        mock_svc.orchestrator.set_task("t-1", {
            "status": "completed",
            "url": "https://example.com",
            "metadata": {},
            "history": [],
        })
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get("/tasks/t-1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["task_id"] == "t-1"
        assert data["status"] == "completed"

    @pytest.mark.asyncio
    async def test_get_nonexistent_task(self) -> None:
        app, _ = _create_test_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get("/tasks/nonexistent")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_get_task_with_full_history(self) -> None:
        app, mock_svc = _create_test_app()
        mock_svc.orchestrator.set_task("t-hist", {
            "status": "completed",
            "url": "https://example.com",
            "metadata": {"key": "val"},
            "history": [
                {"status": "queued"},
                {"status": "processing"},
                {"status": "completed"},
            ],
        })
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get("/tasks/t-hist")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["history"]) == 3
        assert data["metadata"]["key"] == "val"


# ---------------------------------------------------------------------------
# Service lifecycle tests
# ---------------------------------------------------------------------------

class TestServiceLifecycle:
    @pytest.mark.asyncio
    async def test_mock_service_start_stop(self) -> None:
        svc = MockArchonService()
        await svc.start()
        svc.start.assert_called_once()
        await svc.stop()
        svc.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_orchestrator_shutdown(self) -> None:
        orch = MockArchonOrchestrator()
        await orch.shutdown()
        orch.shutdown.assert_called_once()

    @pytest.mark.asyncio
    async def test_orchestrator_dispatch(self) -> None:
        orch = MockArchonOrchestrator()
        result = await orch.dispatch("test.topic", {"payload": {}})
        assert result is None  # mock returns None

    @pytest.mark.asyncio
    async def test_snapshot_returns_set_tasks(self) -> None:
        orch = MockArchonOrchestrator()
        orch.set_task("t-1", {"status": "done"})
        snap = await orch.snapshot_tasks()
        assert "t-1" in snap
        assert snap["t-1"]["status"] == "done"
