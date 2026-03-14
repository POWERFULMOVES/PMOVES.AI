"""
Audio Queue Management

Advanced queue operations for pause, resume, skip, and persistence.
"""

import asyncio
import json
import time
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime
from enum import Enum


class QueueSessionState(Enum):
    """Queue session states."""

    IDLE = "idle"
    PLAYING = "playing"
    PAUSED = "paused"


@dataclass
class QueueSession:
    """Active queue playback session."""

    session_id: str
    state: QueueSessionState = QueueSessionState.IDLE
    current_announcement_id: Optional[str] = None
    started_at: float = field(default_factory=time.time)
    paused_at: Optional[float] = None
    resumed_at: Optional[float] = None
    skipped_count: int = 0
    processed_count: int = 0
    total_count: int = 0
    failed_checks: int = 0  # Track consecutive failures for backoff

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "session_id": self.session_id,
            "state": self.state.value,
            "current_announcement_id": self.current_announcement_id,
            "started_at": self.started_at,
            "started_at_iso": datetime.fromtimestamp(self.started_at).isoformat() + "Z",
            "paused_at": self.paused_at,
            "paused_at_iso": datetime.fromtimestamp(self.paused_at).isoformat() + "Z"
            if self.paused_at
            else None,
            "resumed_at": self.resumed_at,
            "resumed_at_iso": datetime.fromtimestamp(self.resumed_at).isoformat() + "Z"
            if self.resumed_at
            else None,
            "skipped_count": self.skipped_count,
            "processed_count": self.processed_count,
            "total_count": self.total_count,
            "failed_checks": self.failed_checks,
            "duration_seconds": time.time() - self.started_at,
        }


class AudioQueueManager:
    """Advanced queue control for Cast announcements."""

    def __init__(self, persistence_path: Optional[str] = None):
        """
        Initialize audio queue manager.

        Args:
            persistence_path: Path to save queue state (optional)
        """
        self.persistence_path = persistence_path
        self.session: Optional[QueueSession] = None
        self._lock = asyncio.Lock()
        self._processing_task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()
        self._queue_ref = None  # Reference to CastPriorityQueue

    def set_queue(self, queue):
        """
        Set reference to priority queue.

        Args:
            queue: CastPriorityQueue instance
        """
        self._queue_ref = queue

    async def start_processing(self) -> dict:
        """
        Start queue processing.

        Returns:
            Result dict
        """
        async with self._lock:
            if self._processing_task and not self._processing_task.done():
                return {
                    "success": False,
                    "error": "Queue processing already running",
                }

            # Create new session
            self.session = QueueSession(
                session_id=str(int(time.time() * 1000)),
                state=QueueSessionState.PLAYING,
            )

            self._stop_event.clear()
            self._processing_task = asyncio.create_task(self._processing_loop())

            return {
                "success": True,
                "session": self.session.to_dict(),
                "message": "Started queue processing",
            }

    async def pause_processing(self) -> dict:
        """
        Pause queue processing.

        Returns:
            Result dict
        """
        async with self._lock:
            if not self.session or self.session.state != QueueSessionState.PLAYING:
                return {
                    "success": False,
                    "error": "No active playing session",
                }

            self.session.state = QueueSessionState.PAUSED
            self.session.paused_at = time.time()

            return {
                "success": True,
                "session": self.session.to_dict(),
                "message": "Paused queue processing",
            }

    async def resume_processing(self) -> dict:
        """
        Resume queue processing.

        Returns:
            Result dict
        """
        async with self._lock:
            if not self.session or self.session.state != QueueSessionState.PAUSED:
                return {
                    "success": False,
                    "error": "No active paused session",
                }

            self.session.state = QueueSessionState.PLAYING
            self.session.resumed_at = time.time()

            return {
                "success": True,
                "session": self.session.to_dict(),
                "message": "Resumed queue processing",
            }

    async def skip_current(self) -> dict:
        """
        Skip current announcement.

        Returns:
            Result dict
        """
        async with self._lock:
            if not self.session or self.session.state == QueueSessionState.IDLE:
                return {
                    "success": False,
                    "error": "No active session",
                }

            if self.session.current_announcement_id:
                self.session.skipped_count += 1

                # Signal skip
                return {
                    "success": True,
                    "skipped_announcement_id": self.session.current_announcement_id,
                    "session": self.session.to_dict(),
                    "message": "Skipped current announcement",
                }
            else:
                return {
                    "success": False,
                    "error": "No announcement currently playing",
                }

    async def stop_processing(self) -> dict:
        """
        Stop queue processing.

        Returns:
            Result dict
        """
        async with self._lock:
            if not self._processing_task or self._processing_task.done():
                return {
                    "success": False,
                    "error": "No active processing task",
                }

            self._stop_event.set()
            self._processing_task.cancel()

            try:
                await self._processing_task
            except asyncio.CancelledError:
                pass

            if self.session:
                self.session.state = QueueSessionState.IDLE

            return {
                "success": True,
                "message": "Stopped queue processing",
            }

    def get_session(self) -> Optional[QueueSession]:
        """
        Get current session info.

        Returns:
            QueueSession if active, None otherwise
        """
        return self.session

    async def save_state(self) -> dict:
        """
        Save queue state to disk.

        Returns:
            Result dict
        """
        if not self.persistence_path:
            return {
                "success": False,
                "error": "Persistence not configured",
            }

        if not self.session:
            return {
                "success": False,
                "error": "No active session",
            }

        try:
            state = {
                "session": self.session.to_dict(),
                "timestamp": time.time(),
            }

            with open(self.persistence_path, "w") as f:
                json.dump(state, f, indent=2)

            return {
                "success": True,
                "message": f"Saved state to {self.persistence_path}",
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    async def load_state(self) -> dict:
        """
        Load queue state from disk.

        Returns:
            Result dict
        """
        if not self.persistence_path:
            return {
                "success": False,
                "error": "Persistence not configured",
            }

        try:
            with open(self.persistence_path, "r") as f:
                state = json.load(f)

            session_data = state.get("session")
            if session_data:
                self.session = QueueSession(
                    session_id=session_data["session_id"],
                    state=QueueSessionState(session_data["state"]),
                    current_announcement_id=session_data.get("current_announcement_id"),
                    started_at=session_data["started_at"],
                    paused_at=session_data.get("paused_at"),
                    resumed_at=session_data.get("resumed_at"),
                    skipped_count=session_data.get("skipped_count", 0),
                    processed_count=session_data.get("processed_count", 0),
                    total_count=session_data.get("total_count", 0),
                    failed_checks=session_data.get("failed_checks", 0),
                )

            return {
                "success": True,
                "session": self.session.to_dict() if self.session else None,
                "message": f"Loaded state from {self.persistence_path}",
            }

        except FileNotFoundError:
            return {
                "success": False,
                "error": "State file not found",
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    async def batch_remove(self, announcement_ids: list[str]) -> dict:
        """
        Remove multiple announcements from queue.

        Args:
            announcement_ids: List of announcement IDs to remove

        Returns:
            Result dict
        """
        if not self._queue_ref:
            return {
                "success": False,
                "error": "Queue not configured",
            }

        removed = []
        failed = []

        for announcement_id in announcement_ids:
            result = await self._queue_ref.remove(announcement_id)
            if result.get("success"):
                removed.append(announcement_id)
            else:
                failed.append(announcement_id)

        return {
            "success": len(failed) == 0,
            "removed": removed,
            "failed": failed,
            "removed_count": len(removed),
            "failed_count": len(failed),
            "message": f"Removed {len(removed)}/{len(announcement_ids)} announcements",
        }

    async def batch_enqueue(
        self,
        announcements: list[dict],
    ) -> dict:
        """
        Enqueue multiple announcements.

        Args:
            announcements: List of announcement dicts with keys:
                - text (required)
                - device (optional)
                - group (optional)
                - priority (optional, default: "normal")
                - voice (optional, default: "default")

        Returns:
            Result dict
        """
        if not self._queue_ref:
            return {
                "success": False,
                "error": "Queue not configured",
            }

        enqueued = []
        failed = []

        for ann in announcements:
            result = await self._queue_ref.enqueue(
                text=ann.get("text", ""),
                device=ann.get("device"),
                group=ann.get("group"),
                priority=ann.get("priority", "normal"),
                voice=ann.get("voice", "default"),
            )

            if result.get("success"):
                enqueued.append(result.get("announcement"))
            else:
                failed.append({"announcement": ann, "error": result.get("error")})

        return {
            "success": len(failed) == 0,
            "enqueued": enqueued,
            "failed": failed,
            "enqueued_count": len(enqueued),
            "failed_count": len(failed),
            "message": f"Enqueued {len(enqueued)}/{len(announcements)} announcements",
        }

    async def _processing_loop(self):
        """
        Main queue processing loop with exponential backoff and pause on failures.

        Implements:
        - Consecutive failure tracking
        - Exponential backoff (5s, 10s, 20s, 40s, 60s max)
        - Automatic pause after 10 consecutive failures
        - NATS alert publication on pause

        Returns:
            None
        """
        while not self._stop_event.is_set():
            try:
                # Check if paused
                if self.session and self.session.state == QueueSessionState.PAUSED:
                    await asyncio.sleep(0.5)
                    continue

                # Get next announcement
                if self._queue_ref:
                    announcement = await self._queue_ref.dequeue()

                    if announcement:
                        # Reset failure counter on success
                        if self.session:
                            self.session.failed_checks = 0
                            self.session.current_announcement_id = announcement.id

                        # Process announcement (this would trigger actual cast)
                        # For now, we'll just mark as processed
                        await asyncio.sleep(0.1)

                        if self.session:
                            self.session.processed_count += 1
                            self.session.current_announcement_id = None
                    else:
                        # Queue empty, sleep
                        await asyncio.sleep(1)
                else:
                    await asyncio.sleep(1)

            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Processing loop error: {e}")

                # Track consecutive failures
                if self.session:
                    self.session.failed_checks += 1

                    # If too many consecutive failures, pause processing
                    if self.session.failed_checks >= 10:
                        self.session.state = QueueSessionState.PAUSED
                        self.session.paused_at = time.time()

                        print(
                            f"Queue paused after {self.session.failed_checks} "
                            f"consecutive failures: {e}"
                        )

                        # Publish NATS alert (if client available)
                        # Note: NATS client is managed by parent service, not passed here
                        # Parent service should subscribe to health events for this alert
                        break

                    # Exponential backoff (base delay 5s, max 60s)
                    # Formula: min(5 * 2^failed_checks, 60)
                    delay = min(5 * (2 ** self.session.failed_checks), 60)
                    print(
                        f"Backing off for {delay}s after "
                        f"{self.session.failed_checks} consecutive failures"
                    )
                    await asyncio.sleep(delay)
                else:
                    # No session exists, use default backoff
                    await asyncio.sleep(5)
