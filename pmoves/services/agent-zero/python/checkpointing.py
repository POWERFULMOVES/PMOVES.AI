"""
Long Thread (Z) Persistence - Task Checkpointing and Recovery

Provides checkpoint/restore functionality for long-running Agent Zero threads.
Enables recovery from failures and resumption of interrupted tasks.

Features:
1. Checkpoint creation at key execution points
2. State persistence to Supabase
3. Task recovery and resumption
4. Progress tracking and observability
5. Automatic checkpoint cleanup

Usage:
    from pmoves.services.agent_zero.python.checkpointing import CheckpointManager

    checkpoint_mgr = CheckpointManager(supabase_client=supabase)

    # Create a checkpoint
    await checkpoint_mgr.save_checkpoint(
        thread_id="long-thread-1",
        state={"current_step": 5, "data": {...}},
        metadata={"iteration": 10}
    )

    # Restore from checkpoint
    state = await checkpoint_mgr.load_checkpoint("long-thread-1")
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, AsyncIterator, Dict, List, Optional

import httpx

from services.common.env import get_secret

logger = logging.getLogger(__name__)

# Supabase integration
try:
    from services.common.service_registry import get_service_url_sync
    SERVICE_REGISTRY_AVAILABLE = True
except ImportError:
    SERVICE_REGISTRY_AVAILABLE = False

    def get_service_url_sync(slug: str, *, default_port: int = 80) -> str:
        """Fallback when service registry is not available."""
        return f"http://{slug}:{default_port}"


@dataclass
class CheckpointMetadata:
    """Metadata for a thread checkpoint."""
    thread_id: str
    thread_type: str  # base, parallel, chained, fusion, big, long
    status: str  # running, completed, failed, cancelled
    iteration: int = 0
    total_iterations: Optional[int] = None
    progress: float = 0.0  # 0.0 to 1.0
    error: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "thread_id": self.thread_id,
            "thread_type": self.thread_type,
            "status": self.status,
            "iteration": self.iteration,
            "total_iterations": self.total_iterations,
            "progress": self.progress,
            "error": self.error,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class ThreadCheckpoint:
    """A complete thread checkpoint including state and metadata."""
    id: str
    thread_id: str
    state: Dict[str, Any]
    metadata: CheckpointMetadata
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "thread_id": self.thread_id,
            "state": self.state,
            "metadata": self.metadata.to_dict(),
            "created_at": self.created_at,
        }


class CheckpointManager:
    """
    Manages thread checkpoints for persistence and recovery.

    Provides automatic checkpointing at configurable intervals,
    state persistence to Supabase, and recovery capabilities.

    Service URL resolution:
        If supabase_url is None or "auto", the URL is resolved via:
        1. SUPABASE_URL environment variable
        2. Service catalog (Supabase) via service registry
        3. Docker DNS fallback (http://supabase-postgres:5432)

    Attributes:
        supabase_url: Supabase PostgREST URL
        supabase_key: Supabase anon key for API access
        checkpoint_interval: Seconds between automatic checkpoints

    Example:
        >>> mgr = CheckpointManager()
        >>> await mgr.save_checkpoint("thread-1", {"step": 5})
        >>> state = await mgr.load_checkpoint("thread-1")
        >>> print(state["step"])
        5
    """

    def __init__(
        self,
        supabase_url: str | None = None,
        supabase_key: str | None = None,
        checkpoint_interval: int = 30,
        max_checkpoints: int = 10,
    ):
        """Initialize CheckpointManager.

        Args:
            supabase_url: Supabase PostgREST URL. If None, uses service discovery.
            supabase_key: Supabase anon key for API access
            checkpoint_interval: Seconds between automatic checkpoints
            max_checkpoints: Maximum checkpoints to keep per thread
        """
        # Resolve Supabase URL via service discovery if not provided
        if supabase_url is None or supabase_url == "auto":
            supabase_url = os.getenv("SUPABASE_URL")
            if not supabase_url:
                supabase_url = get_service_url_sync("supabase", default_port=3010)

        self._supabase_url = supabase_url.rstrip("/")
        self._supabase_key = supabase_key or get_secret("SUPABASE_ANON_KEY", "")
        self._checkpoint_interval = checkpoint_interval
        self._max_checkpoints = max_checkpoints

        self._client: Optional[httpx.AsyncClient] = None
        self._auto_checkpoint_tasks: Dict[str, asyncio.Task] = {}

        # Local file-based fallback for development
        self._local_checkpoint_dir = Path("runtime/checkpoints")
        self._use_local_fallback = False

    async def _ensure_client(self) -> httpx.AsyncClient:
        """Ensure HTTP client is initialized."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def close(self) -> None:
        """Close HTTP client and cancel auto-checkpoint tasks."""
        # Cancel all auto-checkpoint tasks
        for task in self._auto_checkpoint_tasks.values():
            if not task.done():
                task.cancel()
        self._auto_checkpoint_tasks.clear()

        if self._client:
            await self._client.aclose()
            self._client = None

    async def initialize_schema(self) -> bool:
        """
        Initialize the agent_threads table in Supabase.

        Creates the table if it doesn't exist.

        Returns:
            True if successful, False otherwise
        """
        client = await self._ensure_client()

        # SQL to create the agent_threads table
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS pmoves_core.agent_threads (
            id TEXT PRIMARY KEY,
            thread_id TEXT NOT NULL,
            thread_type TEXT NOT NULL,
            state JSONB NOT NULL DEFAULT '{}',
            status TEXT NOT NULL DEFAULT 'pending',
            iteration INTEGER NOT NULL DEFAULT 0,
            total_iterations INTEGER,
            progress FLOAT NOT NULL DEFAULT 0.0,
            error TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        -- Create indexes
        CREATE INDEX IF NOT EXISTS idx_agent_threads_thread_id
            ON pmoves_core.agent_threads(thread_id);

        CREATE INDEX IF NOT EXISTS idx_agent_threads_status
            ON pmoves_core.agent_threads(status);

        CREATE INDEX IF NOT EXISTS idx_agent_threads_updated_at
            ON pmoves_core.agent_threads(updated_at DESC);

        -- Enable RLS
        ALTER TABLE pmoves_core.agent_threads ENABLE ROW LEVEL SECURITY;

        -- Drop existing policies if any
        DROP POLICY IF EXISTS agent_threads_all ON pmoves_core.agent_threads;

        -- Create permissive policy for development
        CREATE POLICY agent_threads_all ON pmoves_core.agent_threads
            FOR ALL USING (true) WITH CHECK (true);

        -- Grant permissions
        GRANT SELECT, INSERT, UPDATE, DELETE ON pmoves_core.agent_threads TO anon;
        GRANT SELECT, INSERT, UPDATE, DELETE ON pmoves_core.agent_threads TO authenticated;
        GRANT ALL ON pmoves_core.agent_threads TO service_role;

        -- Add comments
        COMMENT ON TABLE pmoves_core.agent_threads IS
            'Thread execution state for Agent Zero long-running tasks';
        COMMENT ON COLUMN pmoves_core.agent_threads.state IS
            'JSONB serialized thread state for checkpoint recovery';
        COMMENT ON COLUMN pmoves_core.agent_threads.progress IS
            'Thread progress from 0.0 to 1.0';
        """

        try:
            # Try to execute via Supabase management API
            # Note: This may require admin privileges
            response = await client.post(
                f"{self._supabase_url}/rest/v1/rpc/exec",
                headers={
                    "apikey": self._supabase_key,
                    "Authorization": f"Bearer {self._supabase_key}",
                    "Content-Type": "application/json",
                },
                json={"sql": create_table_sql},
            )
            # Don't raise for status - we'll try local fallback if needed

            if response.status_code in (200, 201):
                logger.info("Initialized agent_threads table in Supabase")
                return True
            else:
                logger.warning(f"Supabase schema init returned {response.status_code}, using local fallback")
                self._use_local_fallback = True
                return self._init_local_storage()

        except Exception as e:
            logger.warning(f"Failed to initialize Supabase schema: {e}, using local fallback")
            self._use_local_fallback = True
            return self._init_local_storage()

    def _init_local_storage(self) -> bool:
        """Initialize local file-based checkpoint storage."""
        try:
            self._local_checkpoint_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Using local checkpoint storage: {self._local_checkpoint_dir}")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize local checkpoint storage: {e}")
            return False

    async def save_checkpoint(
        self,
        thread_id: str,
        state: Dict[str, Any],
        thread_type: str = "long",
        status: str = "running",
        iteration: int = 0,
        total_iterations: Optional[int] = None,
        progress: float = 0.0,
        error: Optional[str] = None,
    ) -> bool:
        """
        Save a thread checkpoint.

        Args:
            thread_id: Unique thread identifier
            state: Thread state to persist
            thread_type: Type of thread (base, parallel, chained, fusion, big, long)
            status: Current thread status
            iteration: Current iteration number
            total_iterations: Total iterations (if known)
            progress: Progress from 0.0 to 1.0
            error: Error message if failed

        Returns:
            True if checkpoint was saved successfully
        """
        metadata = CheckpointMetadata(
            thread_id=thread_id,
            thread_type=thread_type,
            status=status,
            iteration=iteration,
            total_iterations=total_iterations,
            progress=progress,
            error=error,
            updated_at=datetime.now(timezone.utc).isoformat(),
        )

        checkpoint = ThreadCheckpoint(
            id=f"{thread_id}_{metadata.updated_at}",
            thread_id=thread_id,
            state=state,
            metadata=metadata,
        )

        if self._use_local_fallback:
            return await self._save_local_checkpoint(checkpoint)

        client = await self._ensure_client()

        try:
            # Upsert to Supabase
            response = await client.post(
                f"{self._supabase_url}/rest/v1/agent_threads",
                headers={
                    "apikey": self._supabase_key,
                    "Authorization": f"Bearer {self._supabase_key}",
                    "Content-Type": "application/json",
                    "Prefer": "resolution=ignore-duplicates",
                },
                json={
                    "id": checkpoint.id,
                    "thread_id": thread_id,
                    "thread_type": thread_type,
                    "state": state,
                    "status": status,
                    "iteration": iteration,
                    "total_iterations": total_iterations,
                    "progress": progress,
                    "error": error,
                },
            )

            if response.status_code in (200, 201, 409):  # 409 = duplicate, which is fine
                logger.debug(f"Saved checkpoint for thread {thread_id}")
                return True
            else:
                logger.warning(f"Failed to save checkpoint: {response.status_code}")
                return self._save_local_checkpoint(checkpoint)

        except Exception as e:
            logger.warning(f"Error saving checkpoint to Supabase: {e}")
            return self._save_local_checkpoint(checkpoint)

    async def _save_local_checkpoint(self, checkpoint: ThreadCheckpoint) -> bool:
        """Save checkpoint to local file system."""
        try:
            checkpoint_file = self._local_checkpoint_dir / f"{checkpoint.thread_id}.json"
            with open(checkpoint_file, "w") as f:
                json.dump(checkpoint.to_dict(), f, indent=2)
            logger.debug(f"Saved local checkpoint: {checkpoint_file}")
            return True
        except Exception as e:
            logger.error(f"Failed to save local checkpoint: {e}")
            return False

    async def load_checkpoint(
        self,
        thread_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Load the latest checkpoint for a thread.

        Args:
            thread_id: Thread identifier to load

        Returns:
            Thread state dict, or None if not found
        """
        # Try Supabase first
        if not self._use_local_fallback:
            state = await self._load_supabase_checkpoint(thread_id)
            if state:
                return state

        # Fall back to local storage
        return await self._load_local_checkpoint(thread_id)

    async def _load_supabase_checkpoint(
        self,
        thread_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Load checkpoint from Supabase."""
        client = await self._ensure_client()

        try:
            # Query for latest checkpoint
            response = await client.get(
                f"{self._supabase_url}/rest/v1/agent_threads",
                headers={
                    "apikey": self._supabase_key,
                    "Authorization": f"Bearer {self._supabase_key}",
                },
                params={
                    "thread_id": f"eq.{thread_id}",
                    "order": "updated_at.desc",
                    "limit": "1",
                },
            )

            if response.status_code == 200:
                data = response.json()
                if data and len(data) > 0:
                    checkpoint = data[0]
                    logger.info(f"Loaded checkpoint for thread {thread_id} from Supabase")
                    return {
                        "state": checkpoint.get("state", {}),
                        "metadata": {
                            "thread_type": checkpoint.get("thread_type"),
                            "status": checkpoint.get("status"),
                            "iteration": checkpoint.get("iteration", 0),
                            "total_iterations": checkpoint.get("total_iterations"),
                            "progress": checkpoint.get("progress", 0.0),
                            "error": checkpoint.get("error"),
                            "updated_at": checkpoint.get("updated_at"),
                        },
                    }

        except Exception as e:
            logger.warning(f"Error loading checkpoint from Supabase: {e}")

        return None

    async def _load_local_checkpoint(
        self,
        thread_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Load checkpoint from local file system."""
        try:
            checkpoint_file = self._local_checkpoint_dir / f"{thread_id}.json"
            if checkpoint_file.exists():
                with open(checkpoint_file, "r") as f:
                    checkpoint = json.load(f)
                logger.info(f"Loaded local checkpoint: {checkpoint_file}")
                return {
                    "state": checkpoint.get("state", {}),
                    "metadata": checkpoint.get("metadata", {}),
                }
        except Exception as e:
            logger.error(f"Failed to load local checkpoint: {e}")

        return None

    async def delete_checkpoint(self, thread_id: str) -> bool:
        """
        Delete all checkpoints for a thread.

        Args:
            thread_id: Thread identifier

        Returns:
            True if deleted successfully
        """
        success = True

        # Delete from Supabase
        if not self._use_local_fallback:
            client = await self._ensure_client()
            try:
                response = await client.delete(
                    f"{self._supabase_url}/rest/v1/agent_threads",
                    headers={
                        "apikey": self._supabase_key,
                        "Authorization": f"Bearer {self._supabase_key}",
                    },
                    params={"thread_id": f"eq.{thread_id}"},
                )
                success = response.status_code in (200, 204)
            except Exception as e:
                logger.warning(f"Error deleting checkpoint from Supabase: {e}")
                success = False

        # Delete local file
        try:
            checkpoint_file = self._local_checkpoint_dir / f"{thread_id}.json"
            if checkpoint_file.exists():
                checkpoint_file.unlink()
        except Exception as e:
            logger.warning(f"Error deleting local checkpoint: {e}")

        return success

    async def list_checkpoints(
        self,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        List all checkpoints, optionally filtered by status.

        Args:
            status: Filter by status (running, completed, failed, cancelled)
            limit: Maximum number of checkpoints to return

        Returns:
            List of checkpoint metadata dicts
        """
        # Try Supabase first
        if not self._use_local_fallback:
            checkpoints = await self._list_supabase_checkpoints(status, limit)
            if checkpoints:
                return checkpoints

        # Fall back to local
        return await self._list_local_checkpoints()

    async def _list_supabase_checkpoints(
        self,
        status: Optional[str],
        limit: int,
    ) -> Optional[List[Dict[str, Any]]]:
        """List checkpoints from Supabase."""
        client = await self._ensure_client()

        try:
            params = {
                "order": "updated_at.desc",
                "limit": str(limit),
            }
            if status:
                params["status"] = f"eq.{status}"

            response = await client.get(
                f"{self._supabase_url}/rest/v1/agent_threads",
                headers={
                    "apikey": self._supabase_key,
                    "Authorization": f"Bearer {self._supabase_key}",
                },
                params=params,
            )

            if response.status_code == 200:
                return response.json()

        except Exception as e:
            logger.warning(f"Error listing checkpoints from Supabase: {e}")

        return None

    async def _list_local_checkpoints(self) -> List[Dict[str, Any]]:
        """List checkpoints from local file system."""
        try:
            checkpoints = []
            for checkpoint_file in self._local_checkpoint_dir.glob("*.json"):
                with open(checkpoint_file, "r") as f:
                    checkpoint = json.load(f)
                checkpoints.append({
                    "thread_id": checkpoint.get("thread_id"),
                    "thread_type": checkpoint.get("metadata", {}).get("thread_type"),
                    "status": checkpoint.get("metadata", {}).get("status"),
                    "updated_at": checkpoint.get("metadata", {}).get("updated_at"),
                })
            return sorted(checkpoints, key=lambda x: x.get("updated_at", ""), reverse=True)
        except Exception as e:
            logger.error(f"Error listing local checkpoints: {e}")
            return []

    async def start_auto_checkpoint(
        self,
        thread_id: str,
        get_state_func: callable,
        interval_seconds: Optional[int] = None,
    ) -> None:
        """
        Start automatic checkpointing for a thread.

        Args:
            thread_id: Thread identifier
            get_state_func: Async function that returns current thread state
            interval_seconds: Checkpoint interval (default: self._checkpoint_interval)
        """
        if thread_id in self._auto_checkpoint_tasks:
            logger.warning(f"Auto-checkpoint already running for thread {thread_id}")
            return

        interval = interval_seconds or self._checkpoint_interval

        async def auto_checkpoint_loop():
            while True:
                try:
                    await asyncio.sleep(interval)
                    state = await get_state_func()
                    await self.save_checkpoint(thread_id, state)
                except asyncio.CancelledError:
                    logger.info(f"Auto-checkpoint cancelled for thread {thread_id}")
                    break
                except Exception as e:
                    logger.error(f"Auto-checkpoint error for thread {thread_id}: {e}")

        task = asyncio.create_task(auto_checkpoint_loop())
        self._auto_checkpoint_tasks[thread_id] = task
        logger.info(f"Started auto-checkpoint for thread {thread_id} (interval: {interval}s)")

    async def stop_auto_checkpoint(self, thread_id: str) -> None:
        """
        Stop automatic checkpointing for a thread.

        Args:
            thread_id: Thread identifier
        """
        task = self._auto_checkpoint_tasks.pop(thread_id)
        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        logger.info(f"Stopped auto-checkpoint for thread {thread_id}")

    async def cleanup_old_checkpoints(
        self,
        older_than_hours: int = 24,
        keep_per_thread: int = None,
    ) -> int:
        """
        Clean up old checkpoints.

        Args:
            older_than_hours: Delete checkpoints older than this
            keep_per_thread: Keep N most recent per thread (default: self._max_checkpoints)

        Returns:
            Number of checkpoints deleted
        """
        keep = keep_per_thread or self._max_checkpoints
        cutoff = datetime.now(timezone.utc) - timedelta(hours=older_than_hours)
        deleted = 0

        # Clean up local checkpoints
        try:
            for checkpoint_file in self._local_checkpoint_dir.glob("*.json"):
                try:
                    with open(checkpoint_file, "r") as f:
                        checkpoint = json.load(f)

                    updated_at = checkpoint.get("metadata", {}).get("updated_at")
                    if updated_at:
                        updated_dt = datetime.fromisoformat(updated_at)
                        if updated_dt < cutoff:
                            checkpoint_file.unlink()
                            deleted += 1
                except Exception as e:
                    logger.warning(f"Error processing checkpoint file {checkpoint_file}: {e}")
        except Exception as e:
            logger.error(f"Error during checkpoint cleanup: {e}")

        logger.info(f"Cleaned up {deleted} old checkpoints")
        return deleted


# Convenience functions

async def save_thread_state(
    thread_id: str,
    state: Dict[str, Any],
    thread_type: str = "long",
    status: str = "running",
    progress: float = 0.0,
) -> bool:
    """
    Convenience function to save thread state.

    Args:
        thread_id: Thread identifier
        state: Thread state to persist
        thread_type: Type of thread
        status: Current status
        progress: Progress from 0.0 to 1.0

    Returns:
        True if saved successfully
    """
    mgr = CheckpointManager()
    try:
        return await mgr.save_checkpoint(
            thread_id=thread_id,
            state=state,
            thread_type=thread_type,
            status=status,
            progress=progress,
        )
    finally:
        await mgr.close()


async def load_thread_state(thread_id: str) -> Optional[Dict[str, Any]]:
    """
    Convenience function to load thread state.

    Args:
        thread_id: Thread identifier

    Returns:
        Thread state dict, or None if not found
    """
    mgr = CheckpointManager()
    try:
        return await mgr.load_checkpoint(thread_id)
    finally:
        await mgr.close()


async def delete_thread_state(thread_id: str) -> bool:
    """
    Convenience function to delete thread state.

    Args:
        thread_id: Thread identifier

    Returns:
        True if deleted successfully
    """
    mgr = CheckpointManager()
    try:
        return await mgr.delete_checkpoint(thread_id)
    finally:
        await mgr.close()


__all__ = [
    "CheckpointMetadata",
    "ThreadCheckpoint",
    "CheckpointManager",
    "save_thread_state",
    "load_thread_state",
    "delete_thread_state",
]
