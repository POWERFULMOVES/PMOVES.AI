"""Archon orchestrator primitives.

This module provides the in-memory coordination required for wiring
NATS event subscriptions to the Archon FastAPI application. It exposes
an :class:`ArchonOrchestrator` responsible for dispatching incoming
messages to workflow handlers and for emitting follow-up events using
the shared publish helper provided by :mod:`services.common.events`.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any, Awaitable, Callable, Dict, Iterable, Optional

PublishCallable = Callable[..., Awaitable[Dict[str, Any]]]


class ArchonOrchestrator:
    """Lightweight orchestrator for Archon domain workflows."""

    _CRAWL_TOPICS: Iterable[str] = ("archon.crawl.request", "archon.crawl.request.v1")
    _INGEST_TOPICS: Iterable[str] = (
        "ingest.document.ready.v1",
        "ingest.file.added.v1",
        "ingest.transcript.ready.v1",
    )

    def __init__(self, publish: PublishCallable, *, logger: Optional[logging.Logger] = None) -> None:
        self._publish = publish
        self._logger = logger or logging.getLogger("archon.orchestrator")
        self._tasks: Dict[str, Dict[str, Any]] = {}
        self._lock = asyncio.Lock()
        self._pending: set[asyncio.Task[Any]] = set()
        self._handlers = {
            **{subject: self._handle_crawl_request for subject in self._CRAWL_TOPICS},
            **{subject: self._handle_ingest_event for subject in self._INGEST_TOPICS},
        }

    async def dispatch(self, subject: str, event: Dict[str, Any]) -> Any:
        """Route an event to the appropriate handler."""

        handler = self._handlers.get(subject)
        if handler is None and ".v" in subject:
            handler = self._handlers.get(subject.rsplit(".v", 1)[0])
        if handler is None:
            self._logger.debug("No orchestrator handler registered for subject %s", subject)
            return None
        try:
            return await handler(event)
        except Exception:  # pragma: no cover - defensive logging
            self._logger.exception("Unhandled error in orchestrator handler for %s", subject)
            await self._safe_publish_task_failure(event, subject)
            return None

    async def shutdown(self) -> None:
        """Cancel any background work spawned by the orchestrator."""

        if not self._pending:
            return
        for task in list(self._pending):
            task.cancel()
        await asyncio.gather(*self._pending, return_exceptions=True)
        self._pending.clear()

    async def _handle_crawl_request(self, event: Dict[str, Any]) -> str:
        payload = event.get("payload") or {}
        url = payload.get("url")
        if not url:
            raise ValueError("crawl request missing url")
        task_id = payload.get("task_id") or str(uuid.uuid4())
        metadata = self._coerce_metadata(payload.get("metadata"))
        correlation_id = event.get("correlation_id")
        parent_id = event.get("id")

        await self._record_task_state(task_id, "queued", url=url, extra=metadata)
        await self._publish_task_update(
            task_id,
            status="queued",
            message="crawl accepted",
            correlation_id=correlation_id,
            parent_id=parent_id,
            metadata={"url": url, **metadata},
        )

        self._track(self._process_crawl(task_id, url, metadata, correlation_id, parent_id))
        return task_id

    async def _process_crawl(
        self,
        task_id: str,
        url: str,
        metadata: Dict[str, Any],
        correlation_id: Optional[str],
        parent_id: Optional[str],
    ) -> None:
        try:
            await self._record_task_state(task_id, "processing", url=url, extra=metadata)
            await self._publish_task_update(
                task_id,
                status="processing",
                correlation_id=correlation_id,
                parent_id=parent_id,
                metadata={"url": url, **metadata},
            )

            crawl_result = {
                "task_id": task_id,
                "url": url,
                "status": "completed",
                "metadata": metadata,
                "fragments": metadata.get("fragments", []),
                "extracted_text": metadata.get("extracted_text"),
            }
            await self._publish(
                "archon.crawl.result.v1",
                crawl_result,
                correlation_id=correlation_id,
                parent_id=parent_id,
                source="archon",
            )

            await self._record_task_state(task_id, "completed", url=url, extra=metadata)
            await self._publish_task_update(
                task_id,
                status="completed",
                message="crawl finished",
                correlation_id=correlation_id,
                parent_id=parent_id,
                metadata={"url": url, **metadata},
            )
        except asyncio.CancelledError:  # pragma: no cover - lifecycle management
            raise
        except Exception as exc:  # pragma: no cover - defensive logging
            self._logger.exception("Failed to process crawl request for %s", task_id)
            await self._record_task_state(task_id, "failed", url=url, extra=metadata)
            await self._publish_task_update(
                task_id,
                status="failed",
                message=str(exc),
                correlation_id=correlation_id,
                parent_id=parent_id,
                metadata={"url": url, **metadata},
            )

    async def _handle_ingest_event(self, event: Dict[str, Any]) -> None:
        payload = event.get("payload") or {}
        correlation_id = event.get("correlation_id")
        parent_id = event.get("id")
        subject = event.get("topic")

        task_id = payload.get("task_id") or payload.get("doc_id") or payload.get("file_id")
        if not task_id:
            self._logger.debug("Ingest event missing task identifier: %s", payload)
            return

        metadata = {
            "namespace": payload.get("namespace"),
            "uri": payload.get("uri"),
            "subject": subject,
        }
        metadata = {k: v for k, v in metadata.items() if v is not None}
        await self._record_task_state(task_id, "ingested", extra=metadata)
        await self._publish_task_update(
            task_id,
            status="ingested",
            message="ingestion completed",
            correlation_id=correlation_id,
            parent_id=parent_id,
            metadata=metadata,
        )

    async def _publish_task_update(
        self,
        task_id: str,
        *,
        status: str,
        message: Optional[str] = None,
        correlation_id: Optional[str] = None,
        parent_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        payload: Dict[str, Any] = {"task_id": task_id, "status": status}
        if message:
            payload["message"] = message
        if metadata:
            payload["metadata"] = metadata
        await self._publish(
            "archon.task.update.v1",
            payload,
            correlation_id=correlation_id,
            parent_id=parent_id,
            source="archon",
        )

    async def _record_task_state(
        self,
        task_id: str,
        status: str,
        *,
        url: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> None:
        async with self._lock:
            task = self._tasks.setdefault(task_id, {"history": []})
            task["status"] = status
            if url:
                task["url"] = url
            if extra:
                task.setdefault("metadata", {}).update(extra)
            task["history"].append({"status": status, "ts": asyncio.get_running_loop().time()})

    async def _safe_publish_task_failure(self, event: Dict[str, Any], subject: str) -> None:
        payload = event.get("payload") or {}
        task_id = payload.get("task_id")
        if not task_id:
            return
        await self._publish_task_update(
            task_id,
            status="failed",
            message=f"handler crashed for {subject}",
            correlation_id=event.get("correlation_id"),
            parent_id=event.get("id"),
            metadata=self._coerce_metadata(payload.get("metadata")),
        )

    def _track(self, coro: Awaitable[Any]) -> None:
        task = asyncio.create_task(coro)
        self._pending.add(task)
        task.add_done_callback(self._pending.discard)

    @staticmethod
    def _coerce_metadata(value: Any) -> Dict[str, Any]:
        if isinstance(value, dict):
            return value
        return {}

    async def snapshot_tasks(self) -> Dict[str, Dict[str, Any]]:
        """Return a shallow copy of task state for diagnostics."""

        async with self._lock:
            snapshot: Dict[str, Dict[str, Any]] = {}
            for task_id, data in self._tasks.items():
                snapshot[task_id] = {
                    "status": data.get("status"),
                    "url": data.get("url"),
                    "metadata": dict(data.get("metadata", {})),
                    "history": list(data.get("history", [])),
                }
            return snapshot


__all__ = ["ArchonOrchestrator"]
