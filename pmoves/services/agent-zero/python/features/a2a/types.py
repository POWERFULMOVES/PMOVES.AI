"""
A2A Protocol Type Definitions

Pydantic models for the Agent-to-Agent protocol.
Based on Google's A2A specification and PMOVES-BoTZ patterns.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field, field_validator


class ArtifactType(str, Enum):
    """Types of artifacts that can be produced by agents."""

    TEXT = "text/plain"
    MARKDOWN = "text/markdown"
    JSON = "application/json"
    IMAGE_PNG = "image/png"
    IMAGE_JPEG = "image/jpeg"
    PDF = "application/pdf"
    HTML = "text/html"
    CODE = "text/x-code"
    DATA = "application/x-data"


class TaskStatus(str, Enum):
    """Status of an A2A task through its lifecycle."""

    # Task has been submitted but not yet processed
    SUBMITTED = "submitted"

    # Task is actively being processed
    WORKING = "working"

    # Task requires additional input from the user
    INPUT_REQUIRED = "input-required"

    # Task completed successfully
    COMPLETED = "completed"

    # Task failed with an error
    FAILED = "failed"

    # Task was cancelled before completion
    CANCELLED = "cancelled"


class Artifact(BaseModel):
    """An artifact produced during task execution."""

    type: ArtifactType = Field(
        ...,
        description="MIME type of the artifact content"
    )
    data: Union[str, bytes, Dict[str, Any]] = Field(
        ...,
        description="Artifact content - text, binary data, or structured data"
    )
    uri: Optional[str] = Field(
        None,
        description="Optional URI reference to external content"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Additional metadata about the artifact"
    )

    class Config:
        use_enum_values = False


class AgentCard(BaseModel):
    """
    Agent identity and capability statement.

    Served at /.well-known/agent.json for discovery by other agents.
    Based on Google's A2A Agent Card specification.
    """

    name: str = Field(
        ...,
        description="Unique identifier/name for this agent",
        examples=["agent-zero", "archon", "research-agent"]
    )
    description: str = Field(
        ...,
        description="Human-readable description of the agent's purpose",
        examples=["PMOVES.AI autonomous agent for general development tasks"]
    )
    version: str = Field(
        ...,
        description="Agent version following semantic versioning",
        examples=["2.0.0"]
    )
    capabilities: List[str] = Field(
        default_factory=list,
        description="List of capabilities this agent provides",
        examples=[["code_generation", "file_operations", "web_search"]]
    )
    input_modalities: List[str] = Field(
        default_factory=lambda: ["text/plain", "application/json"],
        description="Accepted input MIME types"
    )
    output_modalities: List[str] = Field(
        default_factory=lambda: ["text/markdown", "application/json"],
        description="Produced output MIME types"
    )
    authentication: Optional[str] = Field(
        default=None,
        description="Authentication method (e.g., 'bearer_token', 'api_key')",
        examples=["bearer_token"]
    )
    max_instructions: Optional[int] = Field(
        default=100,
        description="Maximum number of concurrent instructions supported"
    )
    max_artifacts: Optional[int] = Field(
        default=50,
        description="Maximum number of artifacts per task"
    )
    endpoints: Optional[Dict[str, str]] = Field(
        default=None,
        description="Additional endpoint URLs for extended functionality"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Additional agent metadata"
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate agent name contains only safe characters."""
        if not v or not v.replace("-", "").replace("_", "").isalnum():
            raise ValueError("Agent name must be alphanumeric with hyphens/underscores")
        return v.lower()

    class Config:
        json_schema_extra = {
            "example": {
                "name": "agent-zero",
                "description": "PMOVES.AI autonomous agent for general development tasks",
                "version": "2.0.0",
                "capabilities": [
                    "code_generation",
                    "file_operations",
                    "command_execution",
                    "web_search",
                    "mcp_tool_use"
                ],
                "input_modalities": ["text/plain", "application/json"],
                "output_modalities": ["text/markdown", "application/json", "text/plain"],
                "authentication": "bearer_token"
            }
        }


class Task(BaseModel):
    """
    An A2A Task representing a unit of work.

    Tasks flow through states: submitted -> working -> (completed|failed|cancelled)
    """

    id: str = Field(
        ...,
        description="Unique task identifier (typically UUID)"
    )
    status: TaskStatus = Field(
        default=TaskStatus.SUBMITTED,
        description="Current status of the task"
    )
    instruction: str = Field(
        ...,
        description="Natural language instruction describing the work to do"
    )
    artifacts: List[Artifact] = Field(
        default_factory=list,
        description="Artifacts produced during task execution"
    )
    error_message: Optional[str] = Field(
        None,
        description="Error message if status is 'failed'"
    )
    created_at: Optional[datetime] = Field(
        default_factory=datetime.utcnow,
        description="Timestamp when task was created"
    )
    updated_at: Optional[datetime] = Field(
        default_factory=datetime.utcnow,
        description="Timestamp when task was last updated"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Additional task metadata"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "status": "working",
                "instruction": "Create a REST API endpoint for user authentication",
                "artifacts": [],
                "created_at": "2026-02-02T12:00:00Z"
            }
        }


class TaskCreateRequest(BaseModel):
    """Request to create a new A2A task."""

    id: str = Field(
        ...,
        description="Unique task identifier (typically UUID)"
    )
    instruction: str = Field(
        ...,
        description="Natural language instruction for the agent"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Optional metadata for the task"
    )
    context: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Additional context for task execution"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "instruction": "Analyze the security implications of this code",
                "metadata": {"priority": "high", "source": "archon"}
            }
        }


class TaskCreateResponse(BaseModel):
    """Response for successful task creation."""

    jsonrpc: str = Field(default="2.0", description="JSON-RPC version")
    id: str = Field(..., description="Request ID echoed back")
    result: Task = Field(..., description="The created task")

    class Config:
        json_schema_extra = {
            "example": {
                "jsonrpc": "2.0",
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "result": {
                    "id": "550e8400-e29b-41d4-a716-446655440000",
                    "status": "submitted",
                    "instruction": "Analyze the security implications of this code"
                }
            }
        }


class JSONRPCError(BaseModel):
    """JSON-RPC 2.0 error response."""

    code: int = Field(
        ...,
        description="Error code (standard JSON-RPC or application-specific)"
    )
    message: str = Field(
        ...,
        description="Human-readable error message"
    )
    data: Optional[Any] = Field(
        None,
        description="Additional error data"
    )

    # Standard JSON-RPC error codes
    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603

    # A2A-specific error codes
    TASK_NOT_FOUND = -32001
    TASK_CANCEL_FAILED = -32002
    INVALID_INSTRUCTION = -32003
    RATE_LIMITED = -32004


class TaskErrorResponse(BaseModel):
    """Error response for task operations."""

    jsonrpc: str = Field(default="2.0", description="JSON-RPC version")
    id: Union[str, None] = Field(..., description="Request ID or null for notifications")
    error: JSONRPCError = Field(..., description="Error details")

    class Config:
        json_schema_extra = {
            "example": {
                "jsonrpc": "2.0",
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "error": {
                    "code": -32001,
                    "message": "Task not found",
                    "data": {"task_id": "550e8400-e29b-41d4-a716-446655440000"}
                }
            }
        }


class AgentDiscoveryRequest(BaseModel):
    """Request for agent discovery."""

    capability_filter: Optional[List[str]] = Field(
        None,
        description="Filter agents by required capabilities"
    )
    modality_filter: Optional[Dict[str, List[str]]] = Field(
        None,
        description="Filter by input/output modalities"
    )


class AgentDiscoveryResponse(BaseModel):
    """Response from agent discovery."""

    agents: List[AgentCard] = Field(
        default_factory=list,
        description="List of discovered agents"
    )
    total: int = Field(
        ...,
        description="Total number of agents discovered"
    )


# Default Agent Card for Agent Zero
AGENT_ZERO_CARD = AgentCard(
    name="agent-zero",
    description="PMOVES.AI autonomous agent for general development tasks. Coordinates multi-agent workflows, executes code, manages files, and integrates with MCP tools.",
    version="2.0.0",
    capabilities=[
        "code_generation",
        "file_operations",
        "command_execution",
        "web_search",
        "mcp_tool_use",
        "task_delegation",
        "multi_agent_coordination"
    ],
    input_modalities=["text/plain", "application/json", "text/markdown"],
    output_modalities=["text/markdown", "application/json", "text/plain"],
    authentication="bearer_token",
    max_instructions=100,
    max_artifacts=50,
    endpoints={
        "tasks": "/a2a/v1/tasks",
        "health": "/healthz",
        "metrics": "/metrics"
    },
    metadata={
        "platform": "PMOVES.AI",
        "orchestrator": "Agent Zero",
        "a2a_version": "1.0.0"
    }
)
