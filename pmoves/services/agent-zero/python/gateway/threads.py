"""
Thread Type Definitions and Execution Templates for Agent Zero

Based on PMOVES-BoTZ thread orchestration patterns.
Defines the 6 core thread types used for multi-agent coordination.

Thread Types:
- Base (B): Single prompt-response interaction
- Parallel (P): Multiple agents working simultaneously
- Chained (C): Sequential agent dependencies
- Fusion (F): Multi-model consensus building
- Big (L): Large-scale autonomous planning
- Long (Z): Long-running background tasks
"""

import asyncio
import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Callable

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ThreadType(Enum):
    """Enumeration of supported thread types."""
    BASE = "base"           # B: Single prompt-response
    PARALLEL = "parallel"   # P: Concurrent execution
    CHAINED = "chained"     # C: Sequential dependencies
    FUSION = "fusion"       # F: Multi-model consensus
    BIG = "big"             # L: Large-scale planning
    LONG = "long"           # Z: Long-running tasks


class ThreadStatus(Enum):
    """Thread execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ThreadResult:
    """Result container for thread execution."""
    thread_id: str
    thread_type: ThreadType
    status: ThreadStatus
    result: Any = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "thread_id": self.thread_id,
            "thread_type": self.thread_type.value,
            "status": self.status.value,
            "result": self.result,
            "error": self.error,
            "metadata": self.metadata,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


class BaseThread(ABC):
    """
    Abstract base class for all thread types.

    Thread execution lifecycle:
    1. Initialize (set up context, agents)
    2. Validate (check preconditions)
    3. Execute (run the thread logic)
    4. Finalize (cleanup, return results)

    Attributes:
        thread_id (str): Unique identifier for the thread
        context (Dict[str, Any]): Execution context containing task data
        agents (List[str]): List of agent identifiers assigned to this thread
        metadata (Dict[str, Any]): Additional metadata for the thread
        status (ThreadStatus): Current execution status
        result (Any): Result data from thread execution
        error (Optional[str]): Error message if execution failed
        started_at (Optional[datetime]): Timestamp when thread started
        completed_at (Optional[datetime]): Timestamp when thread completed
    """

    def __init__(
        self,
        thread_id: str,
        context: Dict[str, Any],
        agents: List[str] = None,
        metadata: Dict[str, Any] = None
    ):
        """
        Initialize a BaseThread instance.

        Args:
            thread_id: Unique identifier for this thread instance
            context: Execution context containing task data, parameters, and state
            agents: Optional list of agent identifiers to use for execution
            metadata: Optional metadata dictionary for tracking and observability

        Examples:
            >>> thread = BaseThread("thread-1", {"task": "data"}, agents=["agent-a"])
            >>> print(thread.thread_id)
            'thread-1'
        """
        self.thread_id = thread_id
        self.context = context
        self.agents = agents or []
        self.metadata = metadata or {}
        self.status = ThreadStatus.PENDING
        self.result = None
        self.error = None
        self.started_at = None
        self.completed_at = None

    @property
    @abstractmethod
    def thread_type(self) -> ThreadType:
        """
        Return the thread type identifier.

        Returns:
            ThreadType enum value indicating the specific thread type

        Examples:
            >>> thread.thread_type
            <ThreadType.BASE>
        """
        pass

    @abstractmethod
    async def execute(self) -> ThreadResult:
        """
        Execute the thread logic.

        This method must be implemented by all thread subclasses to define
        the specific execution logic for that thread type.

        Returns:
            ThreadResult with execution outcome, status, and optional result data

        Examples:
            >>> result = await thread.execute()
            >>> print(result.status)
            <ThreadStatus.COMPLETED>
        """
        pass

    async def validate(self) -> bool:
        """
        Validate preconditions before execution.

        Checks that the thread has a valid context and required parameters.

        Returns:
            True if validation passes, False otherwise

        Examples:
            >>> valid = await thread.validate()
            >>> if not valid:
            ...     print("Thread validation failed")
        """
        if not self.context:
            logger.warning(f"Thread {self.thread_id} has empty context")
            return False
        return True

    def _mark_started(self):
        """
        Mark thread as started.

        Sets status to RUNNING and records start timestamp.

        Examples:
            >>> thread._mark_started()
            >>> thread.status
            <ThreadStatus.RUNNING>
        """
        self.status = ThreadStatus.RUNNING
        self.started_at = datetime.utcnow()
        logger.info(f"Thread {self.thread_id} ({self.thread_type.value}) started")

    def _mark_completed(self, result: Any = None, error: str = None):
        """
        Mark thread as completed.

        Sets completion status, timestamp, result, and optional error.

        Args:
            result: Optional result data from execution
            error: Optional error message if execution failed

        Examples:
            >>> thread._mark_completed(result={"output": "success"})
            >>> thread.status
            <ThreadStatus.COMPLETED>
        """
        self.completed_at = datetime.utcnow()
        self.result = result
        self.error = error

        if error:
            self.status = ThreadStatus.FAILED
            logger.error(f"Thread {self.thread_id} failed: {error}")
        else:
            self.status = ThreadStatus.COMPLETED
            logger.info(f"Thread {self.thread_id} completed successfully")

    def to_result(self) -> ThreadResult:
        """
        Convert thread state to ThreadResult.

        Returns:
            ThreadResult object containing current thread state

        Examples:
            >>> result = thread.to_result()
            >>> print(result.thread_id)
            'thread-1'
        """
        return ThreadResult(
            thread_id=self.thread_id,
            thread_type=self.thread_type,
            status=self.status,
            result=self.result,
            error=self.error,
            metadata=self.metadata,
            started_at=self.started_at,
            completed_at=self.completed_at
        )


class BaseSimpleThread(BaseThread):
    """
    Base Thread (B): Single prompt-response interaction.

    The simplest thread type for direct single-agent execution.
    Use for straightforward tasks that don't require coordination.

    Use Cases:
    - Simple queries and responses
    - Single-agent tasks
    - Direct command execution
    - Quick information retrieval

    Example:
        User: "What's the weather today?"
        Agent: [Checks weather service]
        Agent: "It's sunny and 72°F"

    Attributes:
        prompt (str): The primary prompt or task to execute
        agent (Optional[str]): Specific agent to use, if any

    Examples:
        >>> thread = BaseSimpleThread(
        ...     thread_id="base-1",
        ...     context={"query": "weather today"},
        ...     prompt="What's the weather?"
        ... )
        >>> result = await thread.execute()
        >>> print(result.status)
        <ThreadStatus.COMPLETED>
    """

    def __init__(
        self,
        thread_id: str,
        context: Dict[str, Any],
        prompt: str,
        agent: Optional[str] = None,
        agents: List[str] = None,
        metadata: Dict[str, Any] = None
    ):
        """
        Initialize a BaseSimpleThread instance.

        Args:
            thread_id: Unique identifier for this thread
            context: Execution context containing task data
            prompt: The primary prompt or task to execute
            agent: Optional specific agent to use for execution
            agents: Optional list of agents (for compatibility with BaseThread)
            metadata: Optional metadata for tracking

        Examples:
            >>> thread = BaseSimpleThread(
            ...     thread_id="base-1",
            ...     context={"user": "alice"},
            ...     prompt="Summarize the report"
            ... )
        """
        super().__init__(thread_id, context, agents, metadata)
        self.prompt = prompt
        self.agent = agent

    @property
    def thread_type(self) -> ThreadType:
        """Return ThreadType.BASE."""
        return ThreadType.BASE

    async def execute(self) -> ThreadResult:
        """
        Execute the base thread with a single prompt-response interaction.

        This method:
        1. Validates the thread context and prompt
        2. Marks the thread as started
        3. Simulates agent execution (in production, routes to MCP)
        4. Returns the response result

        Returns:
            ThreadResult with the execution outcome and response data

        Examples:
            >>> result = await thread.execute()
            >>> print(result.result)
            {'response': 'Task completed successfully'}
        """
        self._mark_started()

        if not await self.validate():
            self._mark_completed(error="Validation failed: empty context or prompt")
            return self.to_result()

        try:
            logger.info(f"Executing Base thread: {self.prompt[:100]}...")

            # In production: Route to agent via MCP
            # Example: response = await self._route_to_agent(self.prompt, self.agent)
            await asyncio.sleep(0.1)  # Simulate processing

            # Simulate a response
            response = {
                "agent": self.agent or "default",
                "prompt": self.prompt,
                "response": f"Processed: {self.prompt[:50]}...",
                "context_used": bool(self.context)
            }

            self._mark_completed(result=response)
            return self.to_result()

        except Exception as e:
            logger.error(f"Base thread execution failed: {e}")
            self._mark_completed(error=str(e))
            return self.to_result()

    async def validate(self) -> bool:
        """
        Validate preconditions for Base thread execution.

        Checks that both context and prompt are present and non-empty.

        Returns:
            True if validation passes, False otherwise

        Examples:
            >>> is_valid = await thread.validate()
        """
        if not self.context:
            logger.warning(f"Base thread {self.thread_id} has empty context")
            return False

        if not self.prompt:
            logger.warning(f"Base thread {self.thread_id} has empty prompt")
            return False

        return True


class ParallelThread(BaseThread):
    """
    Parallel Thread (P): Multiple agents working simultaneously.

    Use Cases:
    - Divide and conquer tasks
    - Independent subtasks
    - Multi-perspective analysis

    Example:
        Thread 1: Research topic A
        Thread 2: Research topic B
        Thread 3: Research topic C
        -> Wait for all, then merge results
    """

    def __init__(
        self,
        thread_id: str,
        context: Dict[str, Any],
        tasks: List[Dict[str, Any]],
        agents: List[str] = None,
        merge_strategy: str = "concatenate"
    ):
        super().__init__(thread_id, context, agents)
        self.tasks = tasks
        self.merge_strategy = merge_strategy

    @property
    def thread_type(self) -> ThreadType:
        return ThreadType.PARALLEL

    async def execute(self) -> ThreadResult:
        """Execute all tasks in parallel and merge results."""
        self._mark_started()

        if not await self.validate():
            self._mark_completed(error="Validation failed")
            return self.to_result()

        try:
            # Create async tasks for parallel execution
            async def run_task(task: Dict[str, Any]) -> Dict[str, Any]:
                # Simulate task execution
                # In production: route to appropriate agent via MCP
                await asyncio.sleep(0.1)  # Simulate work
                return {
                    "task": task.get("name", "unknown"),
                    "status": "completed",
                    "result": f"Result for {task.get('prompt', 'task')}"
                }

            # Execute all tasks concurrently
            results = await asyncio.gather(
                *[run_task(task) for task in self.tasks],
                return_exceptions=True
            )

            # Merge results based on strategy
            if self.merge_strategy == "concatenate":
                merged = [r for r in results if not isinstance(r, Exception)]
            elif self.merge_strategy == "summarize":
                merged = {"summary": f"Completed {len(results)} parallel tasks"}
            else:
                merged = results

            self._mark_completed(result=merged)
            return self.to_result()

        except Exception as e:
            self._mark_completed(error=str(e))
            return self.to_result()


class ChainedThread(BaseThread):
    """
    Chained Thread (C): Sequential agent dependencies.

    Use Cases:
    - Multi-step workflows
    - Staged processing
    - Agent handoffs

    Example:
        Architect (plan) -> Builder (implement) -> Auditor (review)
        Each agent receives output from previous
    """

    def __init__(
        self,
        thread_id: str,
        context: Dict[str, Any],
        stages: List[Dict[str, Any]],
        agents: List[str] = None
    ):
        super().__init__(thread_id, context, agents)
        self.stages = stages

    @property
    def thread_type(self) -> ThreadType:
        return ThreadType.CHAINED

    async def execute(self) -> ThreadResult:
        """Execute stages sequentially, passing context between them."""
        self._mark_started()

        if not await self.validate():
            self._mark_completed(error="Validation failed")
            return self.to_result()

        try:
            current_context = self.context.copy()
            stage_results = []

            for i, stage in enumerate(self.stages):
                logger.info(f"Executing stage {i+1}/{len(self.stages)}: {stage.get('name', 'unknown')}")

                # Simulate stage execution
                # In production: route to agent via MCP
                await asyncio.sleep(0.1)

                stage_result = {
                    "stage": stage.get("name", f"stage_{i}"),
                    "agent": stage.get("agent", "default"),
                    "output": f"Output from stage {i}"
                }

                stage_results.append(stage_result)

                # Pass output to next stage
                current_context[f"stage_{i}_output"] = stage_result["output"]

                # Check for stage failure
                if stage_result.get("status") == "failed":
                    self._mark_completed(error=f"Stage {i} failed")
                    return self.to_result()

            self._mark_completed(result={
                "stages": stage_results,
                "final_context": current_context
            })
            return self.to_result()

        except Exception as e:
            self._mark_completed(error=str(e))
            return self.to_result()


class FusionThread(BaseThread):
    """
    Fusion Thread (F): Multi-model consensus building.

    Use Cases:
    - Critical decisions requiring validation
    - Multi-perspective synthesis
    - Quality assurance

    Example:
        Query 3 different models (Opus, Sonnet, Haiku)
        Compare responses
        Fuse into consensus result
    """

    def __init__(
        self,
        thread_id: str,
        context: Dict[str, Any],
        models: List[str],
        consensus_threshold: float = 0.7
    ):
        super().__init__(thread_id, context)
        self.models = models
        self.consensus_threshold = consensus_threshold

    @property
    def thread_type(self) -> ThreadType:
        return ThreadType.FUSION

    async def execute(self) -> ThreadResult:
        """Query multiple models and fuse responses."""
        self._mark_started()

        if not await self.validate():
            self._mark_completed(error="Validation failed")
            return self.to_result()

        try:
            # Query all models in parallel
            async def query_model(model: str) -> Dict[str, Any]:
                await asyncio.sleep(0.1)  # Simulate model call
                return {
                    "model": model,
                    "response": f"Response from {model}",
                    "confidence": 0.8
                }

            responses = await asyncio.gather(
                *[query_model(model) for model in self.models]
            )

            # Calculate consensus
            avg_confidence = sum(r["confidence"] for r in responses) / len(responses)

            consensus_result = {
                "responses": responses,
                "consensus_reached": avg_confidence >= self.consensus_threshold,
                "confidence_score": avg_confidence,
                "fused_response": responses[0]["response"] if responses else None
            }

            self._mark_completed(result=consensus_result)
            return self.to_result()

        except Exception as e:
            self._mark_completed(error=str(e))
            return self.to_result()


class BigThread(BaseThread):
    """
    Big Thread (L): Large-scale autonomous planning.

    Use Cases:
    - Complex multi-step projects
    - Architecture design
    - System refactoring

    Example:
        Architect creates 50-step plan
        Builder executes in batches
        Auditor validates each batch
        Repeat until complete
    """

    def __init__(
        self,
        thread_id: str,
        context: Dict[str, Any],
        plan_steps: List[Dict[str, Any]],
        batch_size: int = 5
    ):
        super().__init__(thread_id, context)
        self.plan_steps = plan_steps
        self.batch_size = batch_size

    @property
    def thread_type(self) -> ThreadType:
        return ThreadType.BIG

    async def execute(self) -> ThreadResult:
        """Execute large plan in batches with validation."""
        self._mark_started()

        if not await self.validate():
            self._mark_completed(error="Validation failed")
            return self.to_result()

        try:
            completed_steps = []
            total_steps = len(self.plan_steps)

            for i in range(0, total_steps, self.batch_size):
                batch = self.plan_steps[i:i + self.batch_size]
                logger.info(f"Executing batch {i//self.batch_size + 1}: steps {i+1}-{min(i+self.batch_size, total_steps)}/{total_steps}")

                # Execute batch
                batch_results = []
                for step in batch:
                    await asyncio.sleep(0.05)  # Simulate step execution
                    batch_results.append({
                        "step": step.get("name", "unknown"),
                        "status": "completed",
                        "output": f"Completed {step.get('task', 'task')}"
                    })

                completed_steps.extend(batch_results)

                # Audit batch (simplified)
                # In production: route to Auditor agent
                await asyncio.sleep(0.05)

            self._mark_completed(result={
                "total_steps": total_steps,
                "completed_steps": len(completed_steps),
                "steps": completed_steps
            })
            return self.to_result()

        except Exception as e:
            self._mark_completed(error=str(e))
            return self.to_result()


class LongThread(BaseThread):
    """
    Long Thread (Z): Long-running background tasks.

    Use Cases:
    - Continuous monitoring
    - Periodic data processing
    - Background services

    Example:
        Run indefinitely
        Poll for changes every N seconds
        Process and store results
        Expose status endpoint
    """

    def __init__(
        self,
        thread_id: str,
        context: Dict[str, Any],
        task: Callable,
        interval_seconds: int = 60,
        max_iterations: Optional[int] = None
    ):
        super().__init__(thread_id, context)
        self.task = task
        self.interval_seconds = interval_seconds
        self.max_iterations = max_iterations
        self.iterations = 0
        self._should_stop = False

    @property
    def thread_type(self) -> ThreadType:
        return ThreadType.LONG

    async def execute(self) -> ThreadResult:
        """Run task periodically until stopped."""
        self._mark_started()

        if not await self.validate():
            self._mark_completed(error="Validation failed")
            return self.to_result()

        try:
            while not self._should_stop:
                if self.max_iterations and self.iterations >= self.max_iterations:
                    logger.info(f"Reached max iterations: {self.max_iterations}")
                    break

                self.iterations += 1
                logger.info(f"Long thread iteration {self.iterations}")

                # Execute task
                # In production: await self.task(**self.context)
                await asyncio.sleep(0.1)  # Simulate task work

                # Wait for interval
                await asyncio.sleep(self.interval_seconds)

            self._mark_completed(result={
                "iterations_completed": self.iterations,
                "stopped": self._should_stop
            })
            return self.to_result()

        except Exception as e:
            self._mark_completed(error=str(e))
            return self.to_result()

    def stop(self):
        """Signal the thread to stop gracefully."""
        self._should_stop = True
        logger.info(f"Long thread {self.thread_id} stop requested")


class ThreadFactory:
    """Factory for creating thread instances."""

    @staticmethod
    def create_thread(
        thread_type: ThreadType,
        thread_id: str,
        context: Dict[str, Any],
        **kwargs
    ) -> BaseThread:
        """
        Create a thread instance based on type.

        Args:
            thread_type: Type of thread to create
            thread_id: Unique identifier for the thread
            context: Execution context
            **kwargs: Additional thread-specific parameters

        Returns:
            Instantiated thread object

        Raises:
            ValueError: If thread_type is unknown
        """
        thread_classes = {
            ThreadType.BASE: BaseSimpleThread,
            ThreadType.PARALLEL: ParallelThread,
            ThreadType.CHAINED: ChainedThread,
            ThreadType.FUSION: FusionThread,
            ThreadType.BIG: BigThread,
            ThreadType.LONG: LongThread,
        }

        thread_class = thread_classes.get(thread_type)
        if not thread_class:
            raise ValueError(f"Unknown thread type: {thread_type}")

        return thread_class(thread_id, context, **kwargs)


# Convenience functions for common thread patterns

async def run_base(
    prompt: str,
    context: Dict[str, Any],
    thread_id: str = None,
    agent: Optional[str] = None
) -> ThreadResult:
    """
    Run a simple base thread with a single prompt-response interaction.

    Convenience function for creating and executing a BaseSimpleThread.

    Args:
        prompt: The prompt or task to execute
        context: Execution context containing task data and parameters
        thread_id: Optional thread identifier (auto-generated if not provided)
        agent: Optional specific agent to use for execution

    Returns:
        ThreadResult with the execution outcome and response data

    Examples:
        >>> result = await run_base(
        ...     prompt="What's the weather?",
        ...     context={"location": "San Francisco"}
        ... )
        >>> print(result.status.value)
        'completed'
    """
    if thread_id is None:
        thread_id = f"base-{int(asyncio.get_event_loop().time() * 1000)}"

    thread = BaseSimpleThread(
        thread_id=thread_id,
        context=context,
        prompt=prompt,
        agent=agent
    )
    return await thread.execute()


async def run_parallel(
    tasks: List[Dict[str, Any]],
    context: Dict[str, Any],
    thread_id: str = None
) -> ThreadResult:
    """
    Run multiple tasks in parallel.

    Args:
        tasks: List of task definitions
        context: Shared execution context
        thread_id: Optional thread identifier

    Returns:
        ThreadResult with merged outputs
    """
    if thread_id is None:
        thread_id = f"parallel-{int(asyncio.get_event_loop().time() * 1000)}"

    thread = ParallelThread(
        thread_id=thread_id,
        context=context,
        tasks=tasks
    )
    return await thread.execute()


async def run_chained(
    stages: List[Dict[str, Any]],
    context: Dict[str, Any],
    thread_id: str = None
) -> ThreadResult:
    """
    Run stages in sequence with context passing.

    Args:
        stages: List of stage definitions
        context: Initial execution context
        thread_id: Optional thread identifier

    Returns:
        ThreadResult with final context and stage outputs
    """
    if thread_id is None:
        thread_id = f"chained-{int(asyncio.get_event_loop().time() * 1000)}"

    thread = ChainedThread(
        thread_id=thread_id,
        context=context,
        stages=stages
    )
    return await thread.execute()
