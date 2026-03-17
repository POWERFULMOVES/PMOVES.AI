"""
Priority Queue for Cast Announcements

Ordered queue with priority levels for audio announcements.
"""

import asyncio
import uuid
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime
from enum import IntEnum


# Maximum text length for queue announcements (prevents abuse)
MAX_TEXT_LENGTH = 10000


class Priority(IntEnum):
    """Priority levels for announcements."""

    URGENT = 0
    HIGH = 1
    NORMAL = 2
    LOW = 3


@dataclass
class QueuedAnnouncement:
    """Announcement in the queue."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    text: str = ""
    device: Optional[str] = None
    group: Optional[str] = None
    priority: Priority = Priority.NORMAL
    voice: str = "default"
    created_at: float = field(default_factory=lambda: datetime.utcnow().timestamp())
    meta: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "text": self.text,
            "device": self.device,
            "group": self.group,
            "priority": self.priority.name,
            "voice": self.voice,
            "created_at": self.created_at,
            "created_at_iso": datetime.fromtimestamp(self.created_at).isoformat() + "Z",
            "meta": self.meta,
        }


class CastPriorityQueue:
    """Priority queue for Cast announcements."""

    def __init__(self, max_size: int = 100):
        """
        Initialize priority queue.

        Args:
            max_size: Maximum queue size
        """
        self.max_size = max_size
        self.queues: dict[Priority, list[QueuedAnnouncement]] = {
            p: [] for p in Priority
        }
        self._lock = asyncio.Lock()
        self._processing = False
        self._stop_event = asyncio.Event()

    def _parse_priority(self, priority_str: str) -> Priority:
        """Parse priority string to enum."""
        try:
            return Priority[priority_str.upper()]
        except (KeyError, AttributeError):
            return Priority.NORMAL

    async def enqueue(
        self,
        text: str,
        device: Optional[str] = None,
        group: Optional[str] = None,
        priority: str = "normal",
        voice: str = "default",
        meta: Optional[dict] = None,
    ) -> dict:
        """
        Add announcement to queue with input validation.

        Args:
            text: Text to synthesize (max 10,000 characters)
            device: Device name (optional)
            group: Group name (optional)
            priority: Priority level (urgent/high/normal/low)
            voice: Voice to use
            meta: Additional metadata

        Returns:
            Result dict

        Raises:
            ValueError: If text exceeds MAX_TEXT_LENGTH
        """
        async with self._lock:
            # Validate text length
            if len(text) > MAX_TEXT_LENGTH:
                return {
                    "success": False,
                    "error": f"Text too long (max {MAX_TEXT_LENGTH} characters, got {len(text)})",
                }

            # Check queue size
            total_size = sum(len(q) for q in self.queues.values())
            if total_size >= self.max_size:
                return {
                    "success": False,
                    "error": f"Queue is full (max {self.max_size})",
                }

            priority_enum = self._parse_priority(priority)

            announcement = QueuedAnnouncement(
                text=text,
                device=device,
                group=group,
                priority=priority_enum,
                voice=voice,
                meta=meta or {},
            )

            self.queues[priority_enum].append(announcement)

            # Sort by creation time (FIFO within priority)
            self.queues[priority_enum].sort(key=lambda a: a.created_at)

            return {
                "success": True,
                "announcement": announcement.to_dict(),
                "queue_position": total_size + 1,
                "message": f"Added to queue (priority: {priority_enum.name})",
            }

    async def dequeue(self) -> Optional[QueuedAnnouncement]:
        """
        Get next announcement from queue.

        Returns:
            Next announcement or None if queue is empty
        """
        async with self._lock:
            # Check queues in priority order
            for priority in Priority:
                if self.queues[priority]:
                    return self.queues[priority].pop(0)

            return None

    async def peek(self) -> Optional[QueuedAnnouncement]:
        """
        Peek at next announcement without removing it.

        Returns:
            Next announcement or None if queue is empty
        """
        async with self._lock:
            for priority in Priority:
                if self.queues[priority]:
                    return self.queues[priority][0]

            return None

    def get_queue_status(self) -> dict:
        """
        Get current queue status.

        Returns:
            Queue status dict
        """
        total_size = sum(len(q) for q in self.queues.values())

        return {
            "total": total_size,
            "max_size": self.max_size,
            "available_slots": self.max_size - total_size,
            "by_priority": {
                p.name: len(self.queues[p])
                for p in Priority
            },
            "next_announcement": self.queues[Priority.NORMAL][0].to_dict()
            if self.queues[Priority.NORMAL]
            else None,
        }

    async def clear(self) -> dict:
        """
        Clear all announcements from queue.

        Returns:
            Result dict
        """
        async with self._lock:
            cleared = sum(len(q) for q in self.queues.values())

            for priority in Priority:
                self.queues[priority].clear()

            return {
                "success": True,
                "cleared": cleared,
                "message": f"Cleared {cleared} announcement(s) from queue",
            }

    async def remove(self, announcement_id: str) -> dict:
        """
        Remove specific announcement from queue.

        Args:
            announcement_id: ID of announcement to remove

        Returns:
            Result dict
        """
        async with self._lock:
            for priority in Priority:
                for i, announcement in enumerate(self.queues[priority]):
                    if announcement.id == announcement_id:
                        removed = self.queues[priority].pop(i)
                        return {
                            "success": True,
                            "removed": removed.to_dict(),
                            "message": f"Removed announcement from {priority.name} priority",
                        }

            return {
                "success": False,
                "error": f"Announcement '{announcement_id}' not found",
            }

    def list_announcements(self, priority: Optional[str] = None) -> list[QueuedAnnouncement]:
        """
        List announcements in queue.

        Args:
            priority: Filter by priority (optional)

        Returns:
            List of announcements
        """
        if priority:
            priority_enum = self._parse_priority(priority)
            return self.queues[priority_enum].copy()

        # Return all announcements, ordered by priority
        result = []
        for p in Priority:
            result.extend(self.queues[p])

        return result

    def is_empty(self) -> bool:
        """Check if queue is empty."""
        return all(len(q) == 0 for q in self.queues.values())

    def size(self) -> int:
        """Get total queue size."""
        return sum(len(q) for q in self.queues.values())
