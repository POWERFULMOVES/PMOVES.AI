"""
A2A Server Implementation for Agent Zero

Implements the Agent2Agent protocol for agent interoperability.
Based on PMOVES-BoTZ A2A integration and Google's A2A specification.

Uses lifespan context manager for startup/shutdown events (FastAPI 0.100+ pattern).
"""

import asyncio
import logging
import uuid
from contextlib import asynccontextmanager
from typing import AsyncIterator, Dict, List, Optional

from fastapi import FastAPI, HTTPException, status
from fastapi.responses import JSONResponse
import uvicorn

from .types import (
    AgentCard,
    AgentDiscoveryResponse,
    Artifact,
    ArtifactType,
    Task,
    TaskCreateRequest,
    TaskCreateResponse,
    TaskErrorResponse,
    TaskStatus,
    JSONRPCError,
    AGENT_ZERO_CARD,
)

# Configure logging
logger = logging.getLogger(__name__)

# In-memory task storage (replace with persistent storage in production)
_tasks: Dict[str, Task] = {}
_tasks_lock = asyncio.Lock()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """
    Lifespan context manager for startup and shutdown events.

    This is the recommended pattern for FastAPI 0.100+. Replaces
    deprecated startup/shutdown decorator pattern.

    Yields:
        None: Control is yielded to the application while running
    """
    # Startup: Initialize resources
    logger.info("Starting Agent Zero A2A server...")
    logger.info(f"Agent: {AGENT_ZERO_CARD.name} v{AGENT_ZERO_CARD.version}")
    logger.info(f"Capabilities: {', '.join(AGENT_ZERO_CARD.capabilities)}")

    # Initialize task storage (could connect to database here)
    global _tasks
    _tasks.clear()

    # Yield control to the application
    yield

    # Shutdown: Clean up resources
    logger.info("Shutting down Agent Zero A2A server...")
    logger.info(f"Processed {len(_tasks)} tasks during session")

    # Cleanup task storage
    async with _tasks_lock:
        _tasks.clear()


def create_app(
    agent_card: Optional[AgentCard] = None,
    title: str = "Agent Zero A2A Server",
    version: str = "2.0.0"
) -> FastAPI:
    """
    Create and configure the FastAPI application.

    Args:
        agent_card: Optional custom agent card. Defaults to AGENT_ZERO_CARD.
        title: API title for documentation.
        version: API version.

    Returns:
        Configured FastAPI application instance
    """
    # Use provided card or default
    card = agent_card or AGENT_ZERO_CARD

    # Create FastAPI app with lifespan context manager
    app = FastAPI(
        title=title,
        version=version,
        description="Agent2Agent protocol server for PMOVES.AI Agent Zero",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # Store agent card in app state for access in endpoints
    app.state.agent_card = card

    # Register endpoints
    _register_endpoints(app)

    # Register exception handlers
    _register_exception_handlers(app)

    return app


def _register_endpoints(app: FastAPI) -> None:
    """Register all route handlers with the application."""

    @app.get("/.well-known/agent.json", tags=["Discovery"])
    async def get_agent_card() -> AgentCard:
        """
        Discovery endpoint for A2A clients.

        Returns the Agent Card describing this agent's identity and capabilities.
        This endpoint is standardized for agent discovery across A2A implementations.

        Returns:
            AgentCard: Agent identity and capability statement
        """
        return app.state.agent_card

    @app.get("/healthz", tags=["Health"])
    async def health_check() -> Dict[str, str]:
        """
        Health check endpoint.

        Returns:
            Health status response
        """
        return {
            "status": "healthy",
            "agent": app.state.agent_card.name,
            "version": app.state.agent_card.version
        }

    @app.post("/a2a/v1/tasks", response_model=TaskCreateResponse, tags=["Tasks"])
    async def create_task(request: TaskCreateRequest) -> TaskCreateResponse:
        """
        Create a new task on Agent Zero.

        Accepts an A2A task request and maps it to Agent Zero's context.
        The task is stored and can be queried via GET /a2a/v1/tasks/{task_id}.

        Args:
            request: Task creation request with instruction

        Returns:
            TaskCreateResponse: JSON-RPC 2.0 response with created task

        Raises:
            HTTPException: If task creation fails
        """
        try:
            # Create new task
            task = Task(
                id=request.id,
                status=TaskStatus.SUBMITTED,
                instruction=request.instruction,
                metadata=request.metadata or {}
            )

            # Store task
            async with _tasks_lock:
                _tasks[task.id] = task

            logger.info(f"Task created: {task.id} - {task.instruction[:50]}...")

            # In production, would trigger Agent Zero processing here
            # For now, transition to working state
            task.status = TaskStatus.WORKING
            async with _tasks_lock:
                _tasks[task.id] = task

            return TaskCreateResponse(
                jsonrpc="2.0",
                id=request.id,
                result=task
            )

        except Exception as e:
            logger.error(f"Failed to create task: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create task: {str(e)}"
            )

    @app.get("/a2a/v1/tasks/{task_id}", tags=["Tasks"])
    async def get_task(task_id: str) -> Task:
        """
        Get task status.

        Returns the current state of a task including status and artifacts.

        Args:
            task_id: Unique task identifier

        Returns:
            Task: Current task state

        Raises:
            HTTPException: If task not found
        """
        async with _tasks_lock:
            task = _tasks.get(task_id)

        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=JSONRPCError(
                    code=JSONRPCError.TASK_NOT_FOUND,
                    message="Task not found",
                    data={"task_id": task_id}
                ).model_dump()
            )

        return task

    @app.post("/a2a/v1/tasks/{task_id}/cancel", tags=["Tasks"])
    async def cancel_task(task_id: str) -> Task:
        """
        Cancel a running task.

        Sends a cancel signal to Agent Zero for the specified task.

        Args:
            task_id: Unique task identifier

        Returns:
            Task: Updated task with cancelled status

        Raises:
            HTTPException: If task not found or cannot be cancelled
        """
        async with _tasks_lock:
            task = _tasks.get(task_id)

        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Task not found"
            )

        # Can only cancel submitted or working tasks
        if task.status not in (TaskStatus.SUBMITTED, TaskStatus.WORKING):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot cancel task with status: {task.status}"
            )

        # Update task status
        task.status = TaskStatus.CANCELLED
        async with _tasks_lock:
            _tasks[task_id] = task

        logger.info(f"Task cancelled: {task_id}")

        return task

    @app.post("/a2a/v1/tasks/{task_id}/artifacts", tags=["Tasks"])
    async def add_artifact(
        task_id: str,
        artifact_type: ArtifactType,
        data: str
    ) -> Task:
        """
        Add an artifact to a task.

        Used by Agent Zero to attach output artifacts during task execution.

        Args:
            task_id: Unique task identifier
            artifact_type: MIME type of the artifact
            data: Artifact content

        Returns:
            Task: Updated task with new artifact

        Raises:
            HTTPException: If task not found
        """
        async with _tasks_lock:
            task = _tasks.get(task_id)

        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Task not found"
            )

        # Create and add artifact
        artifact = Artifact(type=artifact_type, data=data)
        task.artifacts.append(artifact)

        # Update task
        async with _tasks_lock:
            _tasks[task_id] = task

        logger.info(f"Artifact added to task {task_id}: {artifact_type}")

        return task

    @app.get("/a2a/v1/tasks", tags=["Tasks"])
    async def list_tasks(
        status_filter: Optional[TaskStatus] = None,
        limit: int = 100
    ) -> List[Task]:
        """
        List all tasks with optional filtering.

        Args:
            status_filter: Optional status filter
            limit: Maximum number of tasks to return

        Returns:
            List of tasks matching the filter
        """
        async with _tasks_lock:
            tasks = list(_tasks.values())

        if status_filter:
            tasks = [t for t in tasks if t.status == status_filter]

        return tasks[:limit]

    @app.post("/a2a/v1/discover", response_model=AgentDiscoveryResponse, tags=["Discovery"])
    async def discover_agents() -> AgentDiscoveryResponse:
        """
        Agent discovery endpoint.

        Returns available agents filtered by capability if requested.
        For Agent Zero, this primarily returns self but can be extended.

        Returns:
            AgentDiscoveryResponse: List of discoverable agents
        """
        return AgentDiscoveryResponse(
            agents=[app.state.agent_card],
            total=1
        )


def _register_exception_handlers(app: FastAPI) -> None:
    """Register custom exception handlers."""

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request, exc):
        """Convert HTTP exceptions to JSON-RPC error responses."""
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": -32000,  # Generic server error
                    "message": exc.detail
                }
            }
        )


def run_server(
    host: str = "0.0.0.0",
    port: int = 8082,
    log_level: str = "info"
) -> None:
    """
    Run the A2A server directly.

    Args:
        host: Host to bind to
        port: Port to bind to
        log_level: Logging level
    """
    app = create_app()

    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level=log_level
    )


# Create default app instance for direct import
app = create_app()


if __name__ == "__main__":
    run_server()
