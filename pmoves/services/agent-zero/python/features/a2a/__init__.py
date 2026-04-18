"""
A2A (Agent-to-Agent) Protocol Implementation for Agent Zero

This module implements the Agent2Agent protocol for interoperability
between agents, based on Google's A2A specification and PMOVES-BoTZ patterns.

Key components:
- AgentCard: Agent identity and capability statement
- Task: A2A task lifecycle management
- Server: FastAPI endpoints for A2A communication
- Client: HTTP client for discovering and communicating with agents

Example:
    from features.a2a import create_a2a_router, AgentCard

    # Mount into existing FastAPI app:
    a2a_router = create_a2a_router()
    app.include_router(a2a_router)
"""

from .types import (
    AgentCard,
    Task,
    TaskStatus,
    Artifact,
    ArtifactType,
    TaskCreateRequest,
    TaskCreateResponse,
    TaskErrorResponse,
    JSONRPCError,
)
from .server import create_app, create_a2a_router, lifespan

__all__ = [
    "AgentCard",
    "Task",
    "TaskStatus",
    "Artifact",
    "ArtifactType",
    "TaskCreateRequest",
    "TaskCreateResponse",
    "TaskErrorResponse",
    "JSONRPCError",
    "create_app",
    "create_a2a_router",
    "lifespan",
]

__version__ = "1.0.0"
