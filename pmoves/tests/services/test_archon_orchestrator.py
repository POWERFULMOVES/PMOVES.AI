"""Comprehensive tests for pmoves.services.archon.orchestrator.

Covers:
- ArchonOrchestrator dispatch routing (crawl, ingest, versioned subjects)
- Crawl request handling (validation, state transitions, publish calls)
- Ingest event handling (metadata extraction, task identification)
- Task state recording and snapshot_tasks
- Background task tracking and shutdown
- Error handling and edge cases
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any, Dict, List
from unittest.mock import AsyncMock

import pytest

from services.archon.orchestrator import ArchonOrchestrator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class PublishCollector:
    """Mock publish callable that records every invocation."""

    def __init__(self) -> None:
        self.calls: List[Dict[str, Any]] = []

    async def __call__(self, topic: str, payload: Any, **kwargs: Any) -> Dict[str, Any]:
        record = {"topic": topic, "payload": payload, **kwargs}
        self.calls.append(record)
        return {"id": str(uuid.uuid4()), "topic": topic, "payload": payload}


@pytest.fixture
def collector() -> PublishCollector:
    return PublishCollector()


@pytest.fixture
def orch(collector: PublishCollector) -> ArchonOrchestrator:
    return ArchonOrchestrator(collector, logger=logging.getLogger("test.orchestrator"))


# ---------------------------------------------------------------------------
# Init / handler registration
# ---------------------------------------------------------------------------

class TestInit:
    def test_handlers_cover_all_well_known_topics(self, orch: ArchonOrchestrator) -> None:
        for topic in ArchonOrchestrator._CRAWL_TOPICS:
            assert topic in orch._handlers
        for topic in ArchonOrchestrator._INGEST_TOPICS:
            assert topic in orch._handlers

    def test_custom_logger(self, collector: PublishCollector) -> None:
        custom_logger = logging.getLogger("custom")
        orch = ArchonOrchestrator(collector, logger=custom_logger)
        assert orch._logger is custom_logger

    def test_default_logger_name(self, collector: PublishCollector) -> None:
        orch = ArchonOrchestrator(collector)
        assert orch._logger.name == "archon.orchestrator"


# ---------------------------------------------------------------------------
# Dispatch routing
# ---------------------------------------------------------------------------

class TestDispatch:
    @pytest.mark.asyncio
    async def test_dispatch_crawl_topic(
        self, orch: ArchonOrchestrator, collector: PublishCollector
    ) -> None:
        event = {
            "id": "ev-1",
            "payload": {"url": "https://example.com", "task_id": "t-1"},
        }
        result = await orch.dispatch("archon.crawl.request", event)
        assert result == "t-1"
        # Wait for background task to complete
        await asyncio.sleep(0.05)
        assert len(collector.calls) >= 2

    @pytest.mark.asyncio
    async def test_dispatch_versioned_crawl_topic(
        self, orch: ArchonOrchestrator, collector: PublishCollector
    ) -> None:
        event = {
            "id": "ev-2",
            "payload": {"url": "https://example.com/v2", "task_id": "t-2"},
        }
        result = await orch.dispatch("archon.crawl.request.v1", event)
        assert result == "t-2"

    @pytest.mark.asyncio
    async def test_dispatch_ingest_topic(
        self, orch: ArchonOrchestrator, collector: PublishCollector
    ) -> None:
        event = {
            "id": "ev-3",
            "topic": "ingest.document.ready.v1",
            "payload": {"doc_id": "d-1", "namespace": "test"},
        }
        result = await orch.dispatch("ingest.document.ready.v1", event)
        assert result is None  # ingest handlers return None

    @pytest.mark.asyncio
    async def test_dispatch_unknown_subject_returns_none(
        self, orch: ArchonOrchestrator
    ) -> None:
        result = await orch.dispatch("unknown.topic", {"payload": {}})
        assert result is None

    @pytest.mark.asyncio
    async def test_dispatch_versioned_fallback(
        self, orch: ArchonOrchestrator, collector: PublishCollector
    ) -> None:
        """Subjects with .v suffix not in handlers map should fall back."""
        event = {
            "id": "ev-4",
            "payload": {"url": "https://example.com/fallback", "task_id": "t-fb"},
        }
        # 'archon.crawl.request.v2' not directly registered but should
        # fall back by stripping .v suffix portion
        result = await orch.dispatch("archon.crawl.request.v2", event)
        # The fallback strips '.v2' -> 'archon.crawl.request' which IS registered
        assert result == "t-fb"

    @pytest.mark.asyncio
    async def test_dispatch_handler_exception_publishes_failure(
        self, collector: PublishCollector
    ) -> None:
        """When a handler raises, dispatch logs + publishes safe failure."""
        async def _failing_publish(*args: Any, **kwargs: Any) -> Dict[str, Any]:
            # The safe failure handler also calls publish; just record it
            collector.calls.append({"_failing": True, "args": args, "kwargs": kwargs})
            return {}

        orch = ArchonOrchestrator(_failing_publish)

        # Send a crawl with no url to trigger ValueError in handler
        event = {
            "id": "ev-err",
            "payload": {"task_id": "t-err"},
        }
        # Monkeypatch _handle_crawl_request to raise after recording
        original = orch._handle_crawl_request
        async def _raise(event: Dict[str, Any]) -> str:
            raise RuntimeError("forced handler crash")

        orch._handlers["archon.crawl.request"] = _raise
        result = await orch.dispatch("archon.crawl.request", event)
        assert result is None
        # Should have published a failure via _safe_publish_task_failure
        assert any("failed" in str(c) for c in collector.calls)


# ---------------------------------------------------------------------------
# Crawl request handling
# ---------------------------------------------------------------------------

class TestCrawlRequest:
    @pytest.mark.asyncio
    async def test_crawl_generates_task_id_when_missing(
        self, orch: ArchonOrchestrator
    ) -> None:
        event = {
            "id": "ev-5",
            "payload": {"url": "https://example.com"},
        }
        result = await orch.dispatch("archon.crawl.request", event)
        assert result is not None
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_crawl_uses_provided_task_id(
        self, orch: ArchonOrchestrator
    ) -> None:
        event = {
            "id": "ev-6",
            "payload": {"url": "https://example.com", "task_id": "custom-tid"},
        }
        result = await orch.dispatch("archon.crawl.request", event)
        assert result == "custom-tid"

    @pytest.mark.asyncio
    async def test_crawl_missing_url_raises(
        self, orch: ArchonOrchestrator
    ) -> None:
        event = {
            "id": "ev-7",
            "payload": {},
        }
        # Dispatch catches exceptions from handlers and returns None
        result = await orch.dispatch("archon.crawl.request", event)
        # The ValueError is caught by dispatch error handler
        assert result is None

    @pytest.mark.asyncio
    async def test_crawl_state_transitions(
        self, orch: ArchonOrchestrator
    ) -> None:
        event = {
            "id": "ev-8",
            "payload": {"url": "https://example.com", "task_id": "t-state"},
        }
        await orch.dispatch("archon.crawl.request", event)
        # Let background task complete
        await asyncio.sleep(0.05)
        snap = await orch.snapshot_tasks()
        task = snap.get("t-state")
        assert task is not None
        assert task["status"] == "completed"
        assert task["url"] == "https://example.com"
        # History should have: queued -> processing -> completed
        statuses = [h["status"] for h in task["history"]]
        assert "queued" in statuses
        assert "processing" in statuses
        assert "completed" in statuses

    @pytest.mark.asyncio
    async def test_crawl_publishes_result_event(
        self, orch: ArchonOrchestrator, collector: PublishCollector
    ) -> None:
        event = {
            "id": "ev-9",
            "correlation_id": "corr-9",
            "payload": {"url": "https://example.com", "task_id": "t-pub"},
        }
        await orch.dispatch("archon.crawl.request", event)
        await asyncio.sleep(0.05)
        # Should have: task.update (queued) -> task.update (processing) -> crawl.result -> task.update (completed)
        topics = [c["topic"] for c in collector.calls]
        assert "archon.crawl.result.v1" in topics
        assert "archon.task.update.v1" in topics

    @pytest.mark.asyncio
    async def test_crawl_result_payload_structure(
        self, orch: ArchonOrchestrator, collector: PublishCollector
    ) -> None:
        event = {
            "id": "ev-10",
            "correlation_id": "corr-10",
            "payload": {
                "url": "https://example.com/struct",
                "task_id": "t-struct",
                "metadata": {"fragments": ["a", "b"], "extracted_text": "hello"},
            },
        }
        await orch.dispatch("archon.crawl.request", event)
        await asyncio.sleep(0.05)
        result_call = next(c for c in collector.calls if c["topic"] == "archon.crawl.result.v1")
        payload = result_call["payload"]
        assert payload["task_id"] == "t-struct"
        assert payload["url"] == "https://example.com/struct"
        assert payload["status"] == "completed"
        assert payload["fragments"] == ["a", "b"]


# ---------------------------------------------------------------------------
# Ingest event handling
# ---------------------------------------------------------------------------

class TestIngestEvent:
    @pytest.mark.asyncio
    async def test_ingest_with_doc_id(
        self, orch: ArchonOrchestrator, collector: PublishCollector
    ) -> None:
        event = {
            "id": "ev-11",
            "correlation_id": "corr-11",
            "topic": "ingest.document.ready.v1",
            "payload": {"doc_id": "d-1", "namespace": "kb", "uri": "file:///x"},
        }
        await orch.dispatch("ingest.document.ready.v1", event)
        snap = await orch.snapshot_tasks()
        assert "d-1" in snap
        assert snap["d-1"]["status"] == "ingested"

    @pytest.mark.asyncio
    async def test_ingest_with_file_id(
        self, orch: ArchonOrchestrator
    ) -> None:
        event = {
            "id": "ev-12",
            "topic": "ingest.file.added.v1",
            "payload": {"file_id": "f-1"},
        }
        await orch.dispatch("ingest.file.added.v1", event)
        snap = await orch.snapshot_tasks()
        assert "f-1" in snap
        assert snap["f-1"]["status"] == "ingested"

    @pytest.mark.asyncio
    async def test_ingest_with_task_id(
        self, orch: ArchonOrchestrator
    ) -> None:
        event = {
            "id": "ev-13",
            "topic": "ingest.transcript.ready.v1",
            "payload": {"task_id": "it-1"},
        }
        await orch.dispatch("ingest.transcript.ready.v1", event)
        snap = await orch.snapshot_tasks()
        assert "it-1" in snap

    @pytest.mark.asyncio
    async def test_ingest_no_identifier_logs_and_returns(
        self, orch: ArchonOrchestrator, collector: PublishCollector
    ) -> None:
        event = {
            "id": "ev-14",
            "topic": "ingest.document.ready.v1",
            "payload": {"namespace": "kb"},  # no doc_id, file_id, task_id
        }
        result = await orch.dispatch("ingest.document.ready.v1", event)
        assert result is None
        snap = await orch.snapshot_tasks()
        # No tasks should have been recorded
        assert len(snap) == 0

    @pytest.mark.asyncio
    async def test_ingest_filters_none_metadata(
        self, orch: ArchonOrchestrator, collector: PublishCollector
    ) -> None:
        event = {
            "id": "ev-15",
            "topic": "ingest.document.ready.v1",
            "payload": {"doc_id": "d-2", "namespace": None},
        }
        await orch.dispatch("ingest.document.ready.v1", event)
        snap = await orch.snapshot_tasks()
        meta = snap["d-2"].get("metadata", {})
        # namespace is None so should be filtered out
        assert "namespace" not in meta

    @pytest.mark.asyncio
    async def test_ingest_publishes_task_update(
        self, orch: ArchonOrchestrator, collector: PublishCollector
    ) -> None:
        event = {
            "id": "ev-16",
            "correlation_id": "corr-16",
            "topic": "ingest.document.ready.v1",
            "payload": {"doc_id": "d-3", "namespace": "test"},
        }
        await orch.dispatch("ingest.document.ready.v1", event)
        # Should have published exactly one task.update
        updates = [c for c in collector.calls if c["topic"] == "archon.task.update.v1"]
        assert len(updates) >= 1
        update = updates[0]
        assert update["payload"]["status"] == "ingested"
        assert update["payload"]["task_id"] == "d-3"
        assert update["correlation_id"] == "corr-16"


# ---------------------------------------------------------------------------
# Task state management
# ---------------------------------------------------------------------------

class TestTaskState:
    @pytest.mark.asyncio
    async def test_record_task_state_creates_entry(self, orch: ArchonOrchestrator) -> None:
        await orch._record_task_state("t-100", "pending")
        snap = await orch.snapshot_tasks()
        assert "t-100" in snap
        assert snap["t-100"]["status"] == "pending"

    @pytest.mark.asyncio
    async def test_record_task_state_with_url(self, orch: ArchonOrchestrator) -> None:
        await orch._record_task_state("t-101", "queued", url="https://example.com")
        snap = await orch.snapshot_tasks()
        assert snap["t-101"]["url"] == "https://example.com"

    @pytest.mark.asyncio
    async def test_record_task_state_with_extra_metadata(
        self, orch: ArchonOrchestrator
    ) -> None:
        await orch._record_task_state("t-102", "processing", extra={"key": "val"})
        snap = await orch.snapshot_tasks()
        assert snap["t-102"]["metadata"]["key"] == "val"

    @pytest.mark.asyncio
    async def test_record_task_state_appends_history(
        self, orch: ArchonOrchestrator
    ) -> None:
        await orch._record_task_state("t-103", "queued")
        await orch._record_task_state("t-103", "processing")
        await orch._record_task_state("t-103", "completed")
        snap = await orch.snapshot_tasks()
        history = snap["t-103"]["history"]
        assert len(history) == 3
        assert history[0]["status"] == "queued"
        assert history[1]["status"] == "processing"
        assert history[2]["status"] == "completed"
        # Each entry should have a timestamp
        for entry in history:
            assert "ts" in entry

    @pytest.mark.asyncio
    async def test_snapshot_tasks_returns_copy(
        self, orch: ArchonOrchestrator
    ) -> None:
        await orch._record_task_state("t-104", "queued")
        snap = await orch.snapshot_tasks()
        # Mutating snapshot should not affect internal state
        snap["t-104"]["status"] = "mutated"
        snap2 = await orch.snapshot_tasks()
        assert snap2["t-104"]["status"] == "queued"


# ---------------------------------------------------------------------------
# Coerce metadata
# ---------------------------------------------------------------------------

class TestCoerceMetadata:
    def test_dict_passthrough(self) -> None:
        data = {"a": 1, "b": "two"}
        assert ArchonOrchestrator._coerce_metadata(data) == data

    def test_none_returns_empty(self) -> None:
        assert ArchonOrchestrator._coerce_metadata(None) == {}

    def test_string_returns_empty(self) -> None:
        assert ArchonOrchestrator._coerce_metadata("not-a-dict") == {}

    def test_list_returns_empty(self) -> None:
        assert ArchonOrchestrator._coerce_metadata([1, 2, 3]) == {}

    def test_int_returns_empty(self) -> None:
        assert ArchonOrchestrator._coerce_metadata(42) == {}


# ---------------------------------------------------------------------------
# Shutdown
# ---------------------------------------------------------------------------

class TestShutdown:
    @pytest.mark.asyncio
    async def test_shutdown_with_no_pending(self, orch: ArchonOrchestrator) -> None:
        # Should complete without error
        await orch.shutdown()
        assert len(orch._pending) == 0

    @pytest.mark.asyncio
    async def test_shutdown_cancels_pending_tasks(
        self, orch: ArchonOrchestrator
    ) -> None:
        # Manually add a long-running pending task
        async def _long_task() -> None:
            await asyncio.sleep(100)

        orch._track(_long_task())
        assert len(orch._pending) == 1

        await orch.shutdown()
        assert len(orch._pending) == 0

    @pytest.mark.asyncio
    async def test_shutdown_idempotent(self, orch: ArchonOrchestrator) -> None:
        await orch.shutdown()
        await orch.shutdown()  # Second call should be safe


# ---------------------------------------------------------------------------
# _safe_publish_task_failure
# ---------------------------------------------------------------------------

class TestSafePublishTaskFailure:
    @pytest.mark.asyncio
    async def test_publishes_failure_with_task_id(
        self, orch: ArchonOrchestrator, collector: PublishCollector
    ) -> None:
        event = {
            "id": "ev-sf1",
            "correlation_id": "corr-sf1",
            "payload": {"task_id": "t-fail", "metadata": {"x": 1}},
        }
        await orch._safe_publish_task_failure(event, "archon.crawl.request")
        updates = [c for c in collector.calls if c["topic"] == "archon.task.update.v1"]
        assert len(updates) == 1
        assert updates[0]["payload"]["status"] == "failed"
        assert updates[0]["payload"]["task_id"] == "t-fail"

    @pytest.mark.asyncio
    async def test_skips_when_no_task_id(
        self, orch: ArchonOrchestrator, collector: PublishCollector
    ) -> None:
        event = {
            "id": "ev-sf2",
            "payload": {},  # No task_id
        }
        await orch._safe_publish_task_failure(event, "some.subject")
        assert len(collector.calls) == 0


# ---------------------------------------------------------------------------
# Edge cases / integration-style
# ---------------------------------------------------------------------------

class TestEdgeCases:
    @pytest.mark.asyncio
    async def test_concurrent_crawl_requests(
        self, orch: ArchonOrchestrator
    ) -> None:
        events = [
            {
                "id": f"ev-conc-{i}",
                "payload": {"url": f"https://example.com/page/{i}", "task_id": f"t-conc-{i}"},
            }
            for i in range(5)
        ]
        results = await asyncio.gather(
            *[orch.dispatch("archon.crawl.request", e) for e in events]
        )
        await asyncio.sleep(0.1)
        snap = await orch.snapshot_tasks()
        for i in range(5):
            assert f"t-conc-{i}" in snap
            assert snap[f"t-conc-{i}"]["status"] == "completed"

    @pytest.mark.asyncio
    async def test_crawl_with_empty_metadata(
        self, orch: ArchonOrchestrator, collector: PublishCollector
    ) -> None:
        event = {
            "id": "ev-empty-meta",
            "payload": {"url": "https://example.com", "task_id": "t-empty"},
        }
        await orch.dispatch("archon.crawl.request", event)
        await asyncio.sleep(0.05)
        # Should not crash with empty metadata
        snap = await orch.snapshot_tasks()
        assert "t-empty" in snap

    @pytest.mark.asyncio
    async def test_dispatch_with_no_payload_key(
        self, orch: ArchonOrchestrator
    ) -> None:
        event = {"id": "ev-np"}  # No 'payload' key at all
        result = await orch.dispatch("archon.crawl.request", event)
        # Should handle gracefully (no url -> ValueError caught -> None)
        assert result is None
