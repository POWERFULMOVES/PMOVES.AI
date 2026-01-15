"""Priority queue for model load requests."""

import asyncio
import heapq
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import IntEnum
from typing import Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class Priority(IntEnum):
    """Priority levels for model load requests."""

    CRITICAL = 1  # System-critical, e.g., health checks
    HIGH = 3  # User-facing requests
    NORMAL = 5  # Standard priority
    LOW = 7  # Background tasks
    IDLE = 9  # Preloading, speculation


@dataclass(order=True)
class LoadRequest:
    """A request to load a model, ordered by priority and timestamp."""

    priority: int
    timestamp: float = field(compare=True)
    model_id: str = field(compare=False)
    provider: str = field(compare=False)
    session_id: Optional[str] = field(compare=False, default=None)
    callback: Optional[Callable] = field(compare=False, default=None)
    request_id: str = field(compare=False, default="")

    def __post_init__(self):
        if not self.request_id:
            import uuid
            self.request_id = str(uuid.uuid4())
        if not self.timestamp:
            self.timestamp = datetime.now().timestamp()

    @property
    def model_key(self) -> str:
        """Get the combined model key."""
        return f"{self.provider}/{self.model_id}"

    def to_dict(self) -> Dict:
        return {
            "request_id": self.request_id,
            "model_id": self.model_id,
            "provider": self.provider,
            "priority": self.priority,
            "session_id": self.session_id,
            "timestamp": self.timestamp,
            "queued_seconds": datetime.now().timestamp() - self.timestamp,
        }


class PriorityQueue:
    """Priority queue for managing model load requests.

    Uses a min-heap with (priority, timestamp) ordering so that:
    1. Lower priority numbers are processed first
    2. Ties are broken by timestamp (earlier first)
    """

    def __init__(self, max_concurrent: int = 1):
        self._heap: List[LoadRequest] = []
        self._pending: Dict[str, LoadRequest] = {}  # model_key -> request
        self._processing: Dict[str, LoadRequest] = {}  # request_id -> request
        self._lock = asyncio.Lock()
        self._not_empty = asyncio.Event()
        self._max_concurrent = max_concurrent

    async def push(self, request: LoadRequest) -> str:
        """Add a request to the queue.

        If a request for the same model already exists, it will be
        updated if the new priority is higher (lower number).

        Returns the request ID.
        """
        async with self._lock:
            existing = self._pending.get(request.model_key)

            if existing:
                if request.priority < existing.priority:
                    # Higher priority request - update
                    self._remove_from_heap(existing)
                    self._pending[request.model_key] = request
                    heapq.heappush(self._heap, request)
                    logger.debug(
                        f"Updated priority for {request.model_key}: "
                        f"{existing.priority} -> {request.priority}"
                    )
                    return request.request_id
                else:
                    # Lower or equal priority - keep existing
                    logger.debug(
                        f"Ignoring duplicate request for {request.model_key} "
                        f"(existing priority: {existing.priority})"
                    )
                    return existing.request_id

            self._pending[request.model_key] = request
            heapq.heappush(self._heap, request)
            self._not_empty.set()
            logger.debug(f"Queued {request.model_key} with priority {request.priority}")
            return request.request_id

    async def pop(self) -> Optional[LoadRequest]:
        """Get the next request to process.

        Blocks until a request is available.
        Returns None if queue is closed.
        """
        while True:
            async with self._lock:
                if self._heap:
                    request = heapq.heappop(self._heap)
                    if request.model_key in self._pending:
                        del self._pending[request.model_key]
                    self._processing[request.request_id] = request

                    if not self._heap:
                        self._not_empty.clear()

                    return request

            await self._not_empty.wait()

    async def pop_nowait(self) -> Optional[LoadRequest]:
        """Get the next request without blocking.

        Returns None if queue is empty.
        """
        async with self._lock:
            if not self._heap:
                return None

            request = heapq.heappop(self._heap)
            if request.model_key in self._pending:
                del self._pending[request.model_key]
            self._processing[request.request_id] = request

            if not self._heap:
                self._not_empty.clear()

            return request

    async def complete(self, request_id: str) -> None:
        """Mark a request as completed."""
        async with self._lock:
            self._processing.pop(request_id, None)

    async def cancel(self, request_id: str) -> bool:
        """Cancel a pending request.

        Returns True if request was found and cancelled.
        """
        async with self._lock:
            # Check processing first
            if request_id in self._processing:
                logger.warning(f"Cannot cancel request {request_id} - already processing")
                return False

            # Find in heap
            for request in self._heap:
                if request.request_id == request_id:
                    self._remove_from_heap(request)
                    if request.model_key in self._pending:
                        del self._pending[request.model_key]
                    logger.info(f"Cancelled request {request_id}")
                    return True

            return False

    def _remove_from_heap(self, request: LoadRequest) -> None:
        """Remove a specific request from the heap."""
        try:
            self._heap.remove(request)
            heapq.heapify(self._heap)
        except ValueError:
            pass

    @property
    def size(self) -> int:
        """Number of pending requests."""
        return len(self._heap)

    @property
    def processing_count(self) -> int:
        """Number of requests currently being processed."""
        return len(self._processing)

    def is_pending(self, model_key: str) -> bool:
        """Check if a model has a pending request."""
        return model_key in self._pending

    def is_processing(self, model_key: str) -> bool:
        """Check if a model is currently being loaded."""
        return any(r.model_key == model_key for r in self._processing.values())

    def list_pending(self) -> List[Dict]:
        """List all pending requests."""
        return [r.to_dict() for r in sorted(self._heap)]

    def list_processing(self) -> List[Dict]:
        """List all processing requests."""
        return [r.to_dict() for r in self._processing.values()]

    def to_dict(self) -> Dict:
        return {
            "pending_count": self.size,
            "processing_count": self.processing_count,
            "max_concurrent": self._max_concurrent,
            "pending": self.list_pending(),
            "processing": self.list_processing(),
        }
