#!/usr/bin/env python3
"""
Gateway Agent for Agent Zero

Central orchestration layer for multi-agent coordination.
Receives user intent, analyzes task requirements, and dispatches
to appropriate subagents (Architect, Builder, Auditor, Researcher).

Based on PMOVES-BoTZ gateway pattern and aligned roadmap Phase 5.

Features:
- Task dispatch logic with thread type selection
- mprocs remote control integration
- NATS event publishing for cross-service coordination
- Health check and metrics endpoints
"""

import asyncio
import json
import logging
import os
import socket
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gateway.threads import (
    ThreadFactory,
    ThreadType,
    ThreadResult,
    ThreadStatus,
    run_base,
    run_parallel,
    run_chained
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class GatewayConfig:
    """Gateway configuration from environment variables."""

    # mprocs remote control server
    MPROCS_SERVER: str = os.environ.get("MPROCS_SERVER", "127.0.0.1:4050")

    # TensorZero for LLM routing (docked mode)
    TENSORZERO_BASE_URL: str = os.environ.get(
        "TENSORZERO_BASE_URL",
        "http://tensorzero-gateway:3000"
    )

    # NATS for event coordination
    NATS_URL: str = os.environ.get("NATS_URL", "nats://nats:4222")

    # HiRAG for knowledge retrieval
    HIRAG_URL: str = os.environ.get("HIRAG_URL", "http://hirag:8086")

    # Deployment mode
    PMOVES_DOCKED_MODE: bool = os.environ.get("PMOVES_DOCKED_MODE", "false").lower() == "true"

    # Agent role
    AGENT_ROLE: str = os.environ.get("AGENT_ROLE", "gateway")


class TaskAnalyzer:
    """Analyzes task requirements to determine optimal execution strategy."""

    @staticmethod
    def analyze_task(task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze task to determine thread type and agent requirements.

        Args:
            task: Task definition with 'intent', 'context', 'requirements'

        Returns:
            Analysis with recommended thread_type, agents, and strategy
        """
        intent = task.get("intent", "").lower()
        requirements = task.get("requirements", {})
        complexity = requirements.get("complexity", "medium")
        agents_available = requirements.get("agents", ["architect", "builder"])

        # Determine thread type based on intent patterns
        thread_type = ThreadType.BASE
        execution_plan = []

        # Parallel: multiple independent tasks
        if any(kw in intent for kw in ["simultaneous", "parallel", "concurrent", "multiple"]):
            thread_type = ThreadType.PARALLEL
            execution_plan = [{"name": f"subtask_{i}", "prompt": intent} for i in range(3)]

        # Chained: sequential workflow
        elif any(kw in intent for kw in ["then", "after", "sequence", "workflow", "pipeline"]):
            thread_type = ThreadType.CHAINED
            execution_plan = [
                {"name": "plan", "agent": "architect", "task": "Create plan"},
                {"name": "build", "agent": "builder", "task": "Implement plan"},
                {"name": "audit", "agent": "auditor", "task": "Review implementation"}
            ]

        # Fusion: consensus needed
        elif any(kw in intent for kw in ["consensus", "validate", "verify", "review", "approve"]):
            thread_type = ThreadType.FUSION

        # Big: large-scale project
        elif complexity == "large" or any(kw in intent for kw in ["project", "system", "architecture", "refactor"]):
            thread_type = ThreadType.BIG
            execution_plan = [{"name": f"step_{i}", "task": f"Execute step {i}"} for i in range(1, 51)]

        # Long: continuous/monitoring
        elif any(kw in intent for kw in ["monitor", "watch", "continuous", "background", "periodic"]):
            thread_type = ThreadType.LONG

        return {
            "thread_type": thread_type,
            "agents": agents_available,
            "execution_plan": execution_plan,
            "estimated_duration": TaskAnalyzer._estimate_duration(thread_type, complexity),
            "confidence": 0.8
        }

    @staticmethod
    def _estimate_duration(thread_type: ThreadType, complexity: str) -> str:
        """Estimate task duration based on type and complexity."""
        base_durations = {
            ThreadType.BASE: "1-5 minutes",
            ThreadType.PARALLEL: "5-15 minutes",
            ThreadType.CHAINED: "10-30 minutes",
            ThreadType.FUSION: "5-10 minutes",
            ThreadType.BIG: "1-4 hours",
            ThreadType.LONG: "Indefinite"
        }

        duration = base_durations.get(thread_type, "5-15 minutes")

        if complexity == "high":
            # Multiply by 2 for high complexity
            return f"Extended {duration}"
        elif complexity == "low":
            return f"Quick {duration}"

        return duration


class Gateway:
    """
    Gateway Agent for task dispatch and orchestration.

    Responsibilities:
    - Receive user intent and context
    - Analyze task requirements
    - Select appropriate thread type
    - Dispatch to subagents via MCP or direct execution
    - Publish events to NATS
    - Return results to user
    """

    def __init__(self, config: GatewayConfig = None):
        self.config = config or GatewayConfig()
        self.role = self.config.AGENT_ROLE
        self.task_analyzer = TaskAnalyzer()
        self.active_threads: Dict[str, ThreadResult] = {}

        # Event publishing (will be initialized if NATS available)
        self.nats_connected = False

    async def initialize(self):
        """Initialize gateway connections and services."""
        logger.info(f"Initializing Gateway agent (role: {self.role})")

        # Check if docked mode
        if self.config.PMOVES_DOCKED_MODE:
            logger.info("Mode: DOCKED (connected to PMOVES.AI)")
            logger.info(f"  TensorZero: {self.config.TENSORZERO_BASE_URL}")
            logger.info(f"  NATS: {self.config.NATS_URL}")
            logger.info(f"  HiRAG: {self.config.HIRAG_URL}")

            # Try to connect to NATS
            try:
                # In production: import nats and establish connection
                # self.nc = await nats.connect(self.config.NATS_URL)
                # self.nats_connected = True
                logger.info("NATS connection: Would connect (not implemented in this stub)")
            except Exception as e:
                logger.warning(f"NATS connection failed: {e}")
        else:
            logger.info("Mode: STANDALONE")

        # Check mprocs server availability
        mprocs_host, mprocs_port = self.config.MPROCS_SERVER.split(":")
        if self._check_port_open(mprocs_host, int(mprocs_port)):
            logger.info(f"mprocs server: Available at {self.config.MPROCS_SERVER}")
        else:
            logger.warning(f"mprocs server: Not available at {self.config.MPROCS_SERVER}")

        logger.info("Gateway initialization complete")

    def _check_port_open(self, host: str, port: int, timeout: float = 1.0) -> bool:
        """Check if a port is open."""
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return True
        except (socket.timeout, socket.error):
            return False

    async def dispatch_task(self, task: Dict[str, Any]) -> ThreadResult:
        """
        Dispatch a task to the appropriate execution strategy.

        Args:
            task: Task definition with 'intent', 'context', 'requirements'

        Returns:
            ThreadResult with execution outcome
        """
        task_id = task.get("task_id", f"task-{int(asyncio.get_event_loop().time() * 1000)}")

        logger.info(f"Dispatching task {task_id}: {task.get('intent', 'Unknown intent')}")

        # Analyze task requirements
        analysis = self.task_analyzer.analyze_task(task)
        thread_type = analysis["thread_type"]

        logger.info(f"Analysis result:")
        logger.info(f"  Thread type: {thread_type.value}")
        logger.info(f"  Agents: {analysis['agents']}")
        logger.info(f"  Estimated duration: {analysis['estimated_duration']}")

        # Publish task created event
        await self._publish_event("task.created", {
            "task_id": task_id,
            "thread_type": thread_type.value,
            "intent": task.get("intent")
        })

        # Execute using appropriate thread type
        try:
            result = await self._execute_thread(
                thread_type=thread_type,
                task_id=task_id,
                task=task,
                analysis=analysis
            )

            # Store result
            self.active_threads[task_id] = result

            # Publish completion event
            await self._publish_event("task.completed", {
                "task_id": task_id,
                "status": result.status.value,
                "duration_ms": self._calculate_duration(result)
            })

            return result

        except Exception as e:
            logger.error(f"Task execution failed: {e}")
            error_result = ThreadResult(
                thread_id=task_id,
                thread_type=thread_type,
                status=ThreadStatus.FAILED,
                error=str(e)
            )
            self.active_threads[task_id] = error_result
            return error_result

    async def _execute_thread(
        self,
        thread_type: ThreadType,
        task_id: str,
        task: Dict[str, Any],
        analysis: Dict[str, Any]
    ) -> ThreadResult:
        """
        Execute task using the specified thread type.

        Args:
            thread_type: The type of thread to execute
            task_id: Unique identifier for the task
            task: Task definition dictionary
            analysis: Task analysis result with execution plan

        Returns:
            ThreadResult with execution outcome

        Examples:
            >>> result = await gateway._execute_thread(
            ...     ThreadType.BASE,
            ...     "task-1",
            ...     {"intent": "hello"},
            ...     analysis
            ... )
        """
        context = {
            "task": task,
            "analysis": analysis,
            "timestamp": datetime.utcnow().isoformat()
        }

        # Route to appropriate execution function
        if thread_type == ThreadType.BASE:
            return await run_base(
                prompt=task.get("intent", ""),
                context=context,
                thread_id=task_id
            )

        elif thread_type == ThreadType.PARALLEL:
            return await run_parallel(
                tasks=analysis["execution_plan"],
                context=context,
                thread_id=task_id
            )

        elif thread_type == ThreadType.CHAINED:
            return await run_chained(
                stages=analysis["execution_plan"],
                context=context,
                thread_id=task_id
            )

        else:
            # Use factory for other types
            thread = ThreadFactory.create_thread(
                thread_type=thread_type,
                thread_id=task_id,
                context=context,
                **self._get_thread_kwargs(thread_type, analysis)
            )
            return await thread.execute()

    def _get_thread_kwargs(self, thread_type: ThreadType, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get thread-specific keyword arguments from analysis.

        Extracts and formats parameters required for specific thread types
        based on the task analysis.

        Args:
            thread_type: The type of thread being created
            analysis: Task analysis result with execution plan and parameters

        Returns:
            Dictionary of keyword arguments for thread initialization

        Examples:
            >>> kwargs = gateway._get_thread_kwargs(ThreadType.FUSION, analysis)
            >>> print(kwargs)
            {'models': ['opus-4-5', 'sonnet-4-5', 'haiku']}
        """
        if thread_type == ThreadType.FUSION:
            return {"models": ["opus-4-5", "sonnet-4-5", "haiku"]}
        elif thread_type == ThreadType.BIG:
            return {"plan_steps": analysis.get("execution_plan", [])}
        elif thread_type == ThreadType.LONG:
            return {
                "task": lambda: None,  # Placeholder
                "interval_seconds": 60
            }
        return {}

    async def _publish_event(self, event_type: str, data: Dict[str, Any]):
        """Publish event to NATS if connected."""
        if not self.nats_connected:
            return

        # In production: await self.nc.publish(f"agent-zero.{event_type}.v1", json.dumps(data).encode())
        logger.debug(f"Event published: agent-zero.{event_type}.v1 - {data}")

    def _calculate_duration(self, result: ThreadResult) -> Optional[int]:
        """Calculate task duration in milliseconds."""
        if result.started_at and result.completed_at:
            delta = result.completed_at - result.started_at
            return int(delta.total_seconds() * 1000)
        return None

    async def get_thread_status(self, thread_id: str) -> Optional[ThreadResult]:
        """
        Get status of an active or completed thread.

        Args:
            thread_id: Unique identifier of the thread to query

        Returns:
            ThreadResult if found, None otherwise

        Examples:
            >>> result = await gateway.get_thread_status("thread-1")
            >>> if result:
            ...     print(f"Status: {result.status.value}")
        """
        return self.active_threads.get(thread_id)

    async def list_active_threads(self) -> Dict[str, ThreadResult]:
        """
        List all active and completed threads.

        Returns:
            Dictionary mapping thread IDs to their ThreadResult objects

        Examples:
            >>> threads = await gateway.list_active_threads()
            >>> print(f"Total threads: {len(threads)}")
        """
        return self.active_threads.copy()

    async def health_check(self) -> Dict[str, Any]:
        """
        Perform health check and return status.

        Returns:
            Dictionary containing health status, service info, and metrics

        Examples:
            >>> health = await gateway.health_check()
            >>> print(health["status"])
            'healthy'
        """
        return {
            "status": "healthy",
            "service": "Gateway Agent",
            "role": self.role,
            "version": "1.0.0",
            "mode": "docked" if self.config.PMOVES_DOCKED_MODE else "standalone",
            "active_threads": len(self.active_threads),
            "nats_connected": self.nats_connected,
            "timestamp": datetime.utcnow().isoformat()
        }

    async def metrics(self) -> Dict[str, Any]:
        """
        Get Prometheus-style metrics for thread execution.

        Returns:
            Dictionary containing thread execution metrics for observability

        Examples:
            >>> metrics = await gateway.metrics()
            >>> print(f"Total threads: {metrics['thread_executions_total']}")
        """
        # Calculate metrics from active threads
        total_threads = len(self.active_threads)
        completed_threads = sum(
            1 for t in self.active_threads.values()
            if t.status == ThreadStatus.COMPLETED
        )
        failed_threads = sum(
            1 for t in self.active_threads.values()
            if t.status == ThreadStatus.FAILED
        )

        # Count by thread type
        thread_type_counts = {}
        for thread in self.active_threads.values():
            ttype = thread.thread_type.value
            thread_type_counts[ttype] = thread_type_counts.get(ttype, 0) + 1

        # Calculate average duration (in milliseconds)
        durations = []
        for thread in self.active_threads.values():
            if thread.started_at and thread.completed_at:
                delta = thread.completed_at - thread.started_at
                durations.append(int(delta.total_seconds() * 1000))

        avg_duration_ms = sum(durations) / len(durations) if durations else 0

        return {
            "# HELP": "Thread execution metrics for Gateway Agent",
            "# TYPE": "gateway_thread_metrics counter",
            "thread_executions_total": total_threads,
            "thread_executions_completed": completed_threads,
            "thread_executions_failed": failed_threads,
            "thread_executions_by_type": thread_type_counts,
            "thread_duration_avg_ms": avg_duration_ms,
            "gateway_role": self.role,
            "docked_mode": self.config.PMOVES_DOCKED_MODE,
            "nats_connected": self.nats_connected,
            "timestamp": datetime.utcnow().isoformat()
        }


async def main():
    """Main entry point for Gateway agent."""
    logger.info("Starting Gateway agent...")

    # Initialize gateway
    gateway = Gateway()
    await gateway.initialize()

    # Example tasks (in production, would receive from CLI or API)
    example_tasks = [
        {
            "intent": "Create a REST API for user management",
            "requirements": {
                "complexity": "medium",
                "agents": ["architect", "builder"]
            }
        },
        {
            "intent": "Review and audit the authentication module",
            "requirements": {
                "complexity": "low",
                "agents": ["auditor"]
            }
        },
        {
            "intent": "Implement parallel data processing for analytics pipeline",
            "requirements": {
                "complexity": "high",
                "agents": ["builder", "architect"]
            }
        }
    ]

    # Process tasks
    for i, task in enumerate(example_tasks, 1):
        logger.info(f"\n{'='*60}")
        logger.info(f"Processing example task {i}/{len(example_tasks)}")
        logger.info(f"{'='*60}")

        result = await gateway.dispatch_task(task)

        logger.info(f"Result: {result.status.value}")
        if result.error:
            logger.error(f"Error: {result.error}")
        else:
            logger.info(f"Output: {json.dumps(result.result, indent=2)[:200]}...")

    # Display final status
    health = await gateway.health_check()
    logger.info(f"\nGateway health: {json.dumps(health, indent=2)}")

    # Keep running (for mprocs management)
    logger.info("\nGateway ready. Listening for tasks...")
    logger.info("Press Ctrl+C to stop")

    try:
        # In production: would listen on HTTP port or stdin for tasks
        await asyncio.sleep(float('inf'))
    except KeyboardInterrupt:
        logger.info("Shutting down Gateway agent...")


if __name__ == "__main__":
    asyncio.run(main())
