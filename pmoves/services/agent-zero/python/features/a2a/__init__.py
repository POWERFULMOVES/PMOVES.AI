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
    from features.a2a import AgentCard, create_server

    card = AgentCard(
        name="my-agent",
        description="An example agent",
        version="1.0.0",
        capabilities=["task_execution"],
        input_modalities=["text/plain"],
        output_modalities=["text/plain"]
    )
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
from .server import create_app, lifespan

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
    "lifespan",
]

__version__ = "1.0.0"
