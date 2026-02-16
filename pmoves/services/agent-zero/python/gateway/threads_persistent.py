"""
Long Thread (Z) with Persistence - Checkpoint/Recovery for Long-Running Tasks

Extends the LongThread class with automatic checkpointing and recovery.
Enables long-running tasks to survive failures and restarts.

Usage:
    from pmoves.services.agent_zero.python.gateway.threads_persistent import (
        PersistentLongThread,
        ThreadType
    )

    async def my_task(context):
        # Long-running task logic
        return {"result": "done"}

    thread = PersistentLongThread(
        thread_id="monitor-1",
        context={"source": "youtube"},
        task=my_task,
        interval_seconds=60,
        enable_checkpointing=True
    )

    result = await thread.execute()
    # Task state is automatically checkpointed and can be recovered
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Awaitable, Callable, Dict, List, Optional

# Import checkpointing module
try:
    from pmoves.services.agent_zero.python.checkpointing import CheckpointManager
    CHECKPOINTING_AVAILABLE = True
except ImportError:
    CHECKPOINTING_AVAILABLE = False
    CheckpointManager = None

# Import base thread types
from .threads import (
    BaseThread,
    ThreadResult,
    ThreadStatus,
    ThreadType,
)

logger = logging.getLogger(__name__)


class PersistentLongThread(BaseThread):
    """
    Long Thread (Z) with automatic checkpointing and recovery.

    Extends LongThread with:
    - Automatic state checkpointing at configurable intervals
    - Recovery from last checkpoint on restart
    - Progress tracking and persistence
    - Graceful shutdown with final checkpoint

    Use Cases:
    - Continuous monitoring that survives restarts
    - Long-running data processing pipelines
    - Background services with stateful operations

    Example:
        >>> thread = PersistentLongThread(
        ...     thread_id="youtube-monitor",
        ...     context={"channel_id": "UC..."},
        ...     task=process_videos,
        ...     interval_seconds=300,
        ...     enable_checkpointing=True
        ... )
        >>> result = await thread.execute()
        # Can be restarted and will resume from last checkpoint

    Attributes:
        thread_id: Unique identifier for this thread
        context: Execution context containing task data
        task: Async callable to execute periodically
        interval_seconds: Seconds between task executions
        max_iterations: Maximum iterations before stopping (None = infinite)
        enable_checkpointing: Whether to enable automatic checkpointing
        checkpoint_interval: Checkpoint save interval (iterations)
    """

    def __init__(
        self,
        thread_id: str,
        context: Dict[str, Any],
        task: Callable[..., Awaitable[Any]],
        interval_seconds: int = 60,
        max_iterations: Optional[int] = None,
        enable_checkpointing: bool = True,
        checkpoint_interval: int = 1,
        checkpoint_manager: Optional[CheckpointManager] = None,
    ):
        """
        Initialize a PersistentLongThread instance.

        Args:
            thread_id: Unique identifier for this thread
            context: Execution context containing task data and parameters
            task: Async callable to execute periodically
            interval_seconds: Seconds between task executions
            max_iterations: Maximum iterations (None = infinite)
            enable_checkpointing: Enable automatic checkpointing
            checkpoint_interval: Save checkpoint every N iterations
            checkpoint_manager: Optional checkpoint manager instance
        """
        super().__init__(thread_id, context)
        self.task = task
        self.interval_seconds = interval_seconds
        self.max_iterations = max_iterations
        self.iterations = 0
        self._should_stop = False

        # Checkpointing configuration
        self.enable_checkpointing = enable_checkpointing and CHECKPOINTING_AVAILABLE
        self.checkpoint_interval = checkpoint_interval
        self._checkpoint_mgr = checkpoint_manager

        # Recovery state
        self._recovered_state: Optional[Dict[str, Any]] = None
        self._last_checkpoint_iteration = 0

    @property
    def thread_type(self) -> ThreadType:
        """Return ThreadType.LONG."""
        return ThreadType.LONG

    async def execute(self) -> ThreadResult:
        """
        Execute the long-running thread with checkpointing.

        This method:
        1. Attempts to recover from previous checkpoint if available
        2. Executes task periodically
        3. Saves checkpoints at configured intervals
        4. Saves final checkpoint on completion

        Returns:
            ThreadResult with execution outcome and final state
        """
        self._mark_started()

        if not await self.validate():
            self._mark_completed(error="Validation failed")
            return self.to_result()

        # Initialize checkpointing if enabled
        if self.enable_checkpointing:
            await self._init_checkpointing()
            # Try to recover previous state
            await self._recover_checkpoint()

        try:
            while not self._should_stop:
                # Check max iterations
                if self.max_iterations and self.iterations >= self.max_iterations:
                    logger.info(
                        f"Long thread {self.thread_id} "
                        f"reached max iterations: {self.max_iterations}"
                    )
                    break

                self.iterations += 1
                logger.info(
                    f"Long thread {self.thread_id} iteration {self.iterations}"
                )

                # Execute task with recovered state
                try:
                    task_context = {
                        **self.context,
                        **(self._recovered_state or {}),
                        "iteration": self.iterations,
                    }

                    # Execute the task
                    if asyncio.iscoroutinefunction(self.task):
                        task_result = await self.task(**task_context)
                    else:
                        task_result = self.task(**task_context)

                    # Update context with task results
                    if isinstance(task_result, dict):
                        self.context.update(task_result)

                except Exception as e:
                    logger.error(f"Task execution failed: {e}")
                    # Save error checkpoint but continue
                    if self.enable_checkpointing:
                        await self._save_checkpoint(status="running", error=str(e))

                # Checkpoint after task execution
                if self.enable_checkpointing:
                    await self._maybe_checkpoint()

                # Check for stop signal before sleeping
                if self._should_stop:
                    break

                # Wait for interval (with interruptible sleep)
                await self._interruptible_sleep(self.interval_seconds)

            # Mark as completed and save final checkpoint
            status = "cancelled" if self._should_stop else "completed"
            self._mark_completed(result={
                "iterations_completed": self.iterations,
                "stopped": self._should_stop,
                "recovered": self._recovered_state is not None,
            })

            if self.enable_checkpointing:
                await self._save_checkpoint(status=status)

            return self.to_result()

        except Exception as e:
            logger.error(f"Long thread execution failed: {e}")
            self._mark_completed(error=str(e))

            if self.enable_checkpointing:
                await self._save_checkpoint(status="failed", error=str(e))

            return self.to_result()

    async def _init_checkpointing(self) -> None:
        """Initialize checkpointing manager."""
        if self._checkpoint_mgr is None:
            self._checkpoint_mgr = CheckpointManager()

        # Ensure schema exists
        await self._checkpoint_mgr.initialize_schema()

    async def _recover_checkpoint(self) -> None:
        """Attempt to recover from previous checkpoint."""
        if not self._checkpoint_mgr:
            return

        checkpoint = await self._checkpoint_mgr.load_checkpoint(self.thread_id)

        if checkpoint:
            state = checkpoint.get("state", {})
            metadata = checkpoint.get("metadata", {})

            # Restore iteration count
            self.iterations = metadata.get("iteration", 0)
            self._last_checkpoint_iteration = self.iterations

            # Restore state context
            self._recovered_state = state
            self.context.update(state)

            logger.info(
                f"Recovered thread {self.thread_id} from checkpoint: "
                f"iteration {self.iterations}, "
                f"status {metadata.get('status')}"
            )

            # Update status if thread was previously failed
            if metadata.get("status") == "failed":
                logger.warning(f"Thread {self.thread_id} previously failed, retrying...")
        else:
            logger.info(f"No checkpoint found for thread {self.thread_id}, starting fresh")

    async def _maybe_checkpoint(self) -> None:
        """Save checkpoint if interval has passed."""
        if not self._checkpoint_mgr:
            return

        # Check if we should checkpoint
        if self.iterations - self._last_checkpoint_iteration >= self.checkpoint_interval:
            await self._save_checkpoint(status="running")
            self._last_checkpoint_iteration = self.iterations

    async def _save_checkpoint(
        self,
        status: str = "running",
        error: Optional[str] = None,
    ) -> None:
        """Save current state as checkpoint."""
        if not self._checkpoint_mgr:
            return

        # Calculate progress
        progress = 0.0
        if self.max_iterations and self.max_iterations > 0:
            progress = self.iterations / self.max_iterations

        # Build state to save
        state = {
            **self.context,
            "iterations": self.iterations,
            "last_checkpoint_time": datetime.utcnow().isoformat(),
        }

        # Save checkpoint
        await self._checkpoint_mgr.save_checkpoint(
            thread_id=self.thread_id,
            state=state,
            thread_type=self.thread_type.value,
            status=status,
            iteration=self.iterations,
            total_iterations=self.max_iterations,
            progress=progress,
            error=error,
        )

        logger.debug(
            f"Saved checkpoint for thread {self.thread_id}: "
            f"iteration {self.iterations}, "
            f"progress {progress:.2f}"
        )

    async def _interruptible_sleep(self, seconds: int) -> None:
        """Sleep that can be interrupted by stop signal."""
        for _ in range(seconds):
            if self._should_stop:
                break
            await asyncio.sleep(1)

    async def validate(self) -> bool:
        """
        Validate preconditions before execution.

        Returns:
            True if validation passes, False otherwise
        """
        if not self.context:
            logger.warning(f"Long thread {self.thread_id} has empty context")
            return False

        if not self.task:
            logger.warning(f"Long thread {self.thread_id} has no task")
            return False

        return True

    def stop(self) -> None:
        """
        Signal the thread to stop gracefully.

        The thread will complete its current iteration,
        save a final checkpoint, and then stop.
        """
        self._should_stop = True
        logger.info(f"Long thread {self.thread_id} stop requested")

    async def cleanup(self) -> None:
        """Cleanup resources including checkpoint manager."""
        if self._checkpoint_mgr:
            await self._checkpoint_mgr.close()
            self._checkpoint_mgr = None

    @classmethod
    async def resume(
        cls,
        thread_id: str,
        task: Callable[..., Awaitable[Any]],
        interval_seconds: int = 60,
        max_iterations: Optional[int] = None,
        checkpoint_manager: Optional[CheckpointManager] = None,
    ) -> "PersistentLongThread":
        """
        Resume a thread from its last checkpoint.

        Args:
            thread_id: Thread identifier to resume
            task: Async callable to execute
            interval_seconds: Seconds between executions
            max_iterations: Maximum iterations
            checkpoint_manager: Optional checkpoint manager

        Returns:
            PersistentLongThread instance with recovered state
        """
        # Create instance
        thread = cls(
            thread_id=thread_id,
            context={},
            task=task,
            interval_seconds=interval_seconds,
            max_iterations=max_iterations,
            checkpoint_manager=checkpoint_manager,
        )

        # Initialize checkpointing and recover
        await thread._init_checkpointing()
        await thread._recover_checkpoint()

        return thread

    @classmethod
    async def list_active_threads(
        cls,
        checkpoint_manager: Optional[CheckpointManager] = None,
    ) -> List[Dict[str, Any]]:
        """
        List all active threads with checkpoints.

        Args:
            checkpoint_manager: Optional checkpoint manager

        Returns:
            List of active thread metadata
        """
        if checkpoint_manager is None:
            checkpoint_manager = CheckpointManager()

        try:
            checkpoints = await checkpoint_manager.list_checkpoints(
                status="running",
                limit=1000,
            )
            return checkpoints or []
        finally:
            await checkpoint_manager.close()

    @classmethod
    async def delete_thread_state(
        cls,
        thread_id: str,
        checkpoint_manager: Optional[CheckpointManager] = None,
    ) -> bool:
        """
        Delete all state for a thread.

        Args:
            thread_id: Thread identifier
            checkpoint_manager: Optional checkpoint manager

        Returns:
            True if deleted successfully
        """
        if checkpoint_manager is None:
            checkpoint_manager = CheckpointManager()

        try:
            return await checkpoint_manager.delete_checkpoint(thread_id)
        finally:
            await checkpoint_manager.close()


# Convenience functions

async def run_persistent_long_thread(
    thread_id: str,
    task: Callable[..., Awaitable[Any]],
    context: Dict[str, Any],
    interval_seconds: int = 60,
    max_iterations: Optional[int] = None,
    enable_checkpointing: bool = True,
) -> ThreadResult:
    """
    Run a persistent long thread with checkpointing.

    Convenience function for creating and executing a PersistentLongThread.

    Args:
        thread_id: Unique identifier for the thread
        task: Async callable to execute periodically
        context: Execution context
        interval_seconds: Seconds between executions
        max_iterations: Maximum iterations (None = infinite)
        enable_checkpointing: Enable automatic checkpointing

    Returns:
        ThreadResult with execution outcome

    Example:
        >>> async def process_videos(channel_id: str, iteration: int = 0):
        ...     # Process videos
        ...     return {"processed": 10}
        >>> result = await run_persistent_long_thread(
        ...     thread_id="video-processor",
        ...     task=process_videos,
        ...     context={"channel_id": "UC..."},
        ...     interval_seconds=300
        ... )
    """
    thread = PersistentLongThread(
        thread_id=thread_id,
        context=context,
        task=task,
        interval_seconds=interval_seconds,
        max_iterations=max_iterations,
        enable_checkpointing=enable_checkpointing,
    )

    try:
        return await thread.execute()
    finally:
        await thread.cleanup()


async def resume_long_thread(
    thread_id: str,
    task: Callable[..., Awaitable[Any]],
    interval_seconds: int = 60,
    max_iterations: Optional[int] = None,
) -> ThreadResult:
    """
    Resume a previously interrupted long thread.

    Args:
        thread_id: Thread identifier to resume
        task: Async callable to execute
        interval_seconds: Seconds between executions
        max_iterations: Maximum iterations

    Returns:
        ThreadResult with execution outcome

    Example:
        >>> result = await resume_long_thread(
        ...     thread_id="video-processor",
        ...     task=process_videos,
        ...     interval_seconds=300
        ... )
    """
    thread = await PersistentLongThread.resume(
        thread_id=thread_id,
        task=task,
        interval_seconds=interval_seconds,
        max_iterations=max_iterations,
    )

    try:
        return await thread.execute()
    finally:
        await thread.cleanup()


__all__ = [
    "PersistentLongThread",
    "run_persistent_long_thread",
    "resume_long_thread",
]
