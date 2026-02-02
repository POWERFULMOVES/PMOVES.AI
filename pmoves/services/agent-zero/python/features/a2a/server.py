"""
A2A Server Implementation for Agent Zero

Implements the Agent2Agent protocol for agent interoperability.
Based on Google's A2A specification (https://a2aproject.github.io/A2A/)
Normative source: specification/grpc/a2a.proto

A2A Protocol v1.0 - Release Candidate
"""

import asyncio
import logging
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, AsyncIterator, Dict, List, Optional

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
    TaskState,
    TaskStatusMessage,
    Message,
    SendMessageRequest,
    SendMessageResponse,
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

    @app.post("/a2a/v1/tasks", response_model=SendMessageResponse, tags=["Tasks"])
    async def create_task(request: Dict[str, Any]) -> SendMessageResponse:
        """
        Create a new task on Agent Zero (A2A message/send endpoint).

        Accepts an A2A message and creates a task for processing.
        The task is stored and can be queried via GET /a2a/v1/tasks/{task_id}.

        Supports both A2A-compliant format and backward compatible format.

        Args:
            request: Dictionary containing either:
                - A2A format: {"message": {...}, "metadata": {...}}
                - Legacy format: {"id": "...", "instruction": "..."}

        Returns:
            SendMessageResponse: Response with created task or direct message

        Raises:
            HTTPException: If task creation fails
        """
        try:
            # Support backward compatibility with old TaskCreateRequest format
            if "id" in request and "instruction" in request and "message" not in request:
                # Old format - convert to new Message format
                message = Message(
                    message_id=request["id"],
                    context_id=str(uuid.uuid4()),
                    role="user",
                    content=request["instruction"]
                )
                metadata = request.get("metadata", {})
            else:
                # New A2A format
                message_dict = request.get("message", {})
                message = Message(**message_dict)
                metadata = request.get("metadata", {})

            # Generate context_id if not provided
            context_id = message.context_id or str(uuid.uuid4())

            # Generate task ID
            task_id = str(uuid.uuid4())

            # Create new task with A2A-compliant structure
            task = Task(
                id=task_id,
                context_id=context_id,
                status=TaskStatusMessage(
                    state=TaskState.SUBMITTED,
                    timestamp=datetime.now()
                ),
                artifacts=[],
                metadata=metadata
            )

            # Add instruction as PMOVES extension if message content is text
            if isinstance(message.content, str):
                task.instruction = message.content

            # Store task
            async with _tasks_lock:
                _tasks[task.id] = task

            logger.info(f"Task created: {task.id} - context: {context_id}")

            # In production, would trigger Agent Zero processing here
            # For now, transition to working state
            task.status = TaskStatusMessage(
                state=TaskState.WORKING,
                timestamp=datetime.now()
            )
            async with _tasks_lock:
                _tasks[task.id] = task

            return SendMessageResponse(task=task)

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
        if task.status.state not in (TaskState.SUBMITTED, TaskState.WORKING):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot cancel task with status: {task.status.state}"
            )

        # Update task status
        task.status = TaskStatusMessage(
            state=TaskState.CANCELLED,
            timestamp=datetime.now()
        )
        async with _tasks_lock:
            _tasks[task_id] = task

        logger.info(f"Task cancelled: {task_id}")

        return task

    @app.post("/a2a/v1/tasks/{task_id}/artifacts", tags=["Tasks"])
    async def add_artifact(
        task_id: str,
        artifact: Dict[str, Any]
    ) -> Task:
        """
        Add an artifact to a task.

        Used by Agent Zero to attach output artifacts during task execution.

        Args:
            task_id: Unique task identifier
            artifact: Dictionary containing artifact data with 'type' and 'data' fields

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

        # Create and add artifact from request body
        new_artifact = Artifact(
            type=artifact.get("type", "text/plain"),
            data=artifact.get("data", "")
        )
        task.artifacts.append(new_artifact)

        # Update task
        async with _tasks_lock:
            _tasks[task_id] = task

        logger.info(f"Artifact added to task {task_id}: {new_artifact.type}")

        return task

    @app.get("/a2a/v1/tasks", tags=["Tasks"])
    async def list_tasks(
        status_filter: Optional[TaskState] = None,
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
            tasks = [t for t in tasks if t.status.state == status_filter]

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
