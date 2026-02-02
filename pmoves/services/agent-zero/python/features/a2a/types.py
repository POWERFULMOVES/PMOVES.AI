"""
A2A Protocol Type Definitions

Pydantic models for the Agent-to-Agent protocol.
Based on Google's A2A specification (https://a2aproject.github.io/A2A/)
Normative source: specification/grpc/a2a.proto

A2A Protocol v1.0 - Release Candidate
"""

from datetime import datetime
from enum import Enum
from typing import Any, ClassVar, Dict, List, Optional, Union
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


class TaskState(str, Enum):
    """
    Defines the possible lifecycle states of a Task.

    Based on A2A specification TaskState enum.
    """

    # The task is in an unknown or indeterminate state
    UNSPECIFIED = "TASK_STATE_UNSPECIFIED"

    # Represents the status that acknowledges a task is created
    SUBMITTED = "TASK_STATE_SUBMITTED"

    # Represents the status that a task is actively being processed
    WORKING = "TASK_STATE_WORKING"

    # Represents the status a task is finished (terminal state)
    COMPLETED = "TASK_STATE_COMPLETED"

    # Represents the status a task is done but failed (terminal state)
    FAILED = "TASK_STATE_FAILED"

    # Represents the status a task was cancelled before it finished (terminal state)
    CANCELLED = "TASK_STATE_CANCELLED"

    # Represents the status that the task requires information to complete (interrupted state)
    INPUT_REQUIRED = "TASK_STATE_INPUT_REQUIRED"

    # Represents the status that the agent has decided to not perform the task (terminal state)
    REJECTED = "TASK_STATE_REJECTED"

    # Represents the state that some authentication is needed from the upstream client
    AUTH_REQUIRED = "TASK_STATE_AUTH_REQUIRED"


# Backward compatibility alias
TaskStatus = TaskState


class TaskStatusMessage(BaseModel):
    """
    A container for the status of a task.

    Based on A2A specification TaskStatus message.
    """

    state: TaskState = Field(
        ...,
        description="The current state of this task"
    )
    timestamp: datetime = Field(
        default_factory=datetime.now,
        description="ISO 8601 Timestamp when the status was recorded"
    )
    message: Optional[str] = Field(
        None,
        description="A message associated with the status"
    )


class AgentInterface(BaseModel):
    """
    Declares a combination of a target URL and a transport protocol for interacting with the agent.

    Based on A2A specification AgentInterface message.
    """

    url: str = Field(
        ...,
        description="The URL where this interface is available. Must be a valid absolute HTTPS URL in production.",
        examples=["https://api.example.com/a2a/v1", "https://grpc.example.com/a2a"]
    )
    protocol_binding: str = Field(
        ...,
        description="The protocol binding supported at this URL (e.g., 'JSONRPC', 'GRPC', 'HTTP+JSON')",
        examples=["JSONRPC", "GRPC", "HTTP+JSON"]
    )
    tenant: Optional[str] = Field(
        None,
        description="Tenant to be set in the request when calling the agent"
    )


class AgentProvider(BaseModel):
    """Represents the service provider of an agent."""

    url: str = Field(
        ...,
        description="A URL for the agent provider's website or relevant documentation",
        examples=["https://ai.google.dev"]
    )
    organization: str = Field(
        ...,
        description="The name of the agent provider's organization",
        examples=["Google", "PMOVES.AI"]
    )


class AgentCapabilities(BaseModel):
    """Defines optional capabilities supported by an agent."""

    streaming: Optional[bool] = Field(
        None,
        description="Indicates if the agent supports streaming responses"
    )
    push_notifications: Optional[bool] = Field(
        None,
        description="Indicates if the agent supports sending push notifications for asynchronous task updates"
    )
    state_transition_history: Optional[bool] = Field(
        None,
        description="Indicates if the agent provides a history of state transitions for a task"
    )
    extensions: List[str] = Field(
        default_factory=list,
        description="A list of protocol extensions supported by the agent"
    )


class AgentSkill(BaseModel):
    """Represents a distinct capability or function that an agent can perform."""

    id: str = Field(
        ...,
        description="A unique identifier for the agent's skill"
    )
    name: str = Field(
        ...,
        description="A human-readable name for the skill"
    )
    description: str = Field(
        ...,
        description="A detailed description of the skill"
    )
    tags: List[str] = Field(
        default_factory=list,
        description="A set of keywords describing the skill's capabilities"
    )
    examples: List[str] = Field(
        default_factory=list,
        description="Example prompts or scenarios that this skill can handle"
    )
    input_modes: List[str] = Field(
        default_factory=list,
        description="The set of supported input media types for this skill"
    )
    output_modes: List[str] = Field(
        default_factory=list,
        description="The set of supported output media types for this skill"
    )


class SecurityScheme(BaseModel):
    """
    Defines a security scheme that can be used to secure an agent's endpoints.

    Simplified version of OpenAPI 3.2 Security Scheme Object.
    """

    type: str = Field(
        ...,
        description="The type of security scheme (e.g., 'apiKey', 'http', 'oauth2', 'openIdConnect')",
        examples=["apiKey", "http", "oauth2", "openIdConnect"]
    )
    description: Optional[str] = Field(
        None,
        description="An optional description for the security scheme"
    )
    scheme: Optional[str] = Field(
        None,
        description="The name of the HTTP Authentication scheme (e.g., 'Bearer', 'Basic')"
    )
    bearer_format: Optional[str] = Field(
        None,
        description="A hint to the client to identify how the bearer token is formatted (e.g., 'JWT')"
    )


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

    Normative source: A2A proto AgentCard message
    """

    protocol_version: str = Field(
        default="1.0",
        description="The version of the A2A protocol this agent supports",
        examples=["1.0"]
    )
    name: str = Field(
        ...,
        description="A human readable name for the agent",
        examples=["Recipe Agent", "Agent Zero"]
    )
    description: str = Field(
        ...,
        description="A human-readable description of the agent",
        examples=["Agent that helps users with recipes and cooking"]
    )
    supported_interfaces: List[AgentInterface] = Field(
        ...,
        description="Ordered list of supported interfaces. First entry is preferred."
    )
    provider: AgentProvider = Field(
        ...,
        description="The service provider of the agent"
    )
    version: str = Field(
        ...,
        description="The version of the agent",
        examples=["1.0.0"]
    )
    documentation_url: Optional[str] = Field(
        None,
        description="A url to provide additional documentation about the agent"
    )
    capabilities: AgentCapabilities = Field(
        ...,
        description="A2A Capability set supported by the agent"
    )
    security_schemes: Dict[str, SecurityScheme] = Field(
        default_factory=dict,
        description="The security scheme details used for authenticating with this agent"
    )
    default_input_modes: List[str] = Field(
        ...,
        description="The set of interaction modes that the agent supports across all skills",
        examples=[["text/plain", "application/json", "text/markdown"]]
    )
    default_output_modes: List[str] = Field(
        ...,
        description="The media types supported as outputs from this agent",
        examples=[["text/markdown", "application/json", "text/plain"]]
    )
    skills: List[AgentSkill] = Field(
        default_factory=list,
        description="Skills represent an ability of an agent"
    )
    supports_extended_agent_card: Optional[bool] = Field(
        None,
        description="Whether the agent supports providing an extended agent card when authenticated"
    )
    icon_url: Optional[str] = Field(
        None,
        description="An optional URL to an icon for the agent"
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate agent name contains only safe characters."""
        if not v or not v.replace("-", "").replace("_", "").replace(" ", "").isalnum():
            raise ValueError("Agent name must be alphanumeric with hyphens/underscores/spaces")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "protocol_version": "1.0",
                "name": "Agent Zero",
                "description": "PMOVES.AI autonomous agent for general development tasks",
                "supported_interfaces": [
                    {
                        "url": "https://api.pmoves.ai/a2a/v1",
                        "protocol_binding": "JSONRPC"
                    }
                ],
                "provider": {
                    "url": "https://pmoves.ai",
                    "organization": "PMOVES.AI"
                },
                "version": "2.0.0",
                "capabilities": {
                    "streaming": True,
                    "push_notifications": True
                },
                "default_input_modes": ["text/plain", "application/json", "text/markdown"],
                "default_output_modes": ["text/markdown", "application/json", "text/plain"],
                "skills": [
                    {
                        "id": "code_generation",
                        "name": "Code Generation",
                        "description": "Generate code in various programming languages",
                        "tags": ["code", "development", "programming"]
                    }
                ]
            }
        }


class Task(BaseModel):
    """
    An A2A Task representing a unit of work.

    Based on A2A specification Task message.
    Tasks flow through states: submitted -> working -> (completed|failed|cancelled|rejected)
    """

    id: str = Field(
        ...,
        description="Unique identifier (e.g. UUID) for the task, generated by the server"
    )
    context_id: str = Field(
        ...,
        description="Unique identifier (e.g. UUID) for the contextual collection of interactions"
    )
    status: TaskStatusMessage = Field(
        ...,
        description="The current status of a Task, including state and a message"
    )
    artifacts: List[Artifact] = Field(
        default_factory=list,
        description="A set of output artifacts for a Task"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="A key/value object to store custom metadata about a task"
    )

    # PMOVES.AI extension - not in A2A spec
    instruction: Optional[str] = Field(
        None,
        description="Natural language instruction describing the work to do (PMOVES extension)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "context_id": "660e8400-e29b-41d4-a716-446655440001",
                "status": {
                    "state": "TASK_STATE_WORKING",
                    "timestamp": "2026-02-02T12:00:00Z"
                },
                "artifacts": [],
                "instruction": "Create a REST API endpoint for user authentication"
            }
        }


class Message(BaseModel):
    """
    Message is one unit of communication between client and server.

    Based on A2A specification Message message.
    """

    message_id: str = Field(
        ...,
        description="The unique identifier (e.g. UUID) of the message"
    )
    context_id: Optional[str] = Field(
        None,
        description="The context id of the message"
    )
    task_id: Optional[str] = Field(
        None,
        description="The task id of the message"
    )
    role: str = Field(
        ...,
        description="Identifies the sender of the message (user or agent)",
        examples=["user", "agent"]
    )
    content: Union[str, List[Dict[str, Any]]] = Field(
        ...,
        description="The message content - text string or list of parts"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Any optional metadata to provide along with the message"
    )


class SendMessageRequest(BaseModel):
    """
    Represents a request for the message/send method.

    Based on A2A specification SendMessageRequest message.
    """

    message: Message = Field(
        ...,
        description="The message to send to the agent"
    )
    configuration: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Configuration for the send request"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="A flexible key-value map for passing additional context or parameters"
    )

    # PMOVES.AI extension - for backward compatibility
    id: Optional[str] = Field(
        None,
        description="DEPRECATED: Use message.message_id instead (PMOVES extension)"
    )
    instruction: Optional[str] = Field(
        None,
        description="DEPRECATED: Use message.content instead (PMOVES extension)"
    )


class SendMessageResponse(BaseModel):
    """
    Response for message/send operation.

    Based on A2A specification SendMessageResponse message.
    Contains either a Task or a direct Message.
    """

    task: Optional[Task] = Field(
        None,
        description="A task object representing the processing of the message"
    )
    message: Optional[Message] = Field(
        None,
        description="A direct response message (for simple interactions)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "task": {
                    "id": "550e8400-e29b-41d4-a716-446655440000",
                    "context_id": "660e8400-e29b-41d4-a716-446655440001",
                    "status": {
                        "state": "TASK_STATE_SUBMITTED",
                        "timestamp": "2026-02-02T12:00:00Z"
                    },
                    "artifacts": []
                }
            }
        }


# Backward compatibility aliases
TaskCreateRequest = SendMessageRequest
TaskCreateResponse = SendMessageResponse


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
    PARSE_ERROR: ClassVar[int] = -32700
    INVALID_REQUEST: ClassVar[int] = -32600
    METHOD_NOT_FOUND: ClassVar[int] = -32601
    INVALID_PARAMS: ClassVar[int] = -32602
    INTERNAL_ERROR: ClassVar[int] = -32603

    # A2A-specific error codes
    TASK_NOT_FOUND: ClassVar[int] = -32001
    TASK_CANCEL_FAILED: ClassVar[int] = -32002
    INVALID_INSTRUCTION: ClassVar[int] = -32003
    RATE_LIMITED: ClassVar[int] = -32004


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
    protocol_version="1.0",
    name="Agent Zero",
    description="PMOVES.AI autonomous agent for general development tasks. Coordinates multi-agent workflows, executes code, manages files, and integrates with MCP tools.",
    supported_interfaces=[
        AgentInterface(
            url="http://localhost:8082/a2a/v1",
            protocol_binding="JSONRPC"
        )
    ],
    provider=AgentProvider(
        url="https://pmoves.ai",
        organization="PMOVES.AI"
    ),
    version="2.0.0",
    documentation_url="https://docs.pmoves.ai",
    capabilities=AgentCapabilities(
        streaming=True,
        push_notifications=False,
        state_transition_history=False,
        extensions=[]
    ),
    security_schemes={
        "bearer": SecurityScheme(
            type="http",
            description="Bearer token authentication",
            scheme="Bearer",
            bearer_format="JWT"
        )
    },
    default_input_modes=["text/plain", "application/json", "text/markdown"],
    default_output_modes=["text/markdown", "application/json", "text/plain"],
    skills=[
        AgentSkill(
            id="code_generation",
            name="Code Generation",
            description="Generate code in various programming languages",
            tags=["code", "development", "programming"],
            examples=["Write a Python function to parse JSON", "Create a REST API endpoint"]
        ),
        AgentSkill(
            id="file_operations",
            name="File Operations",
            description="Read, write, and manipulate files",
            tags=["files", "io", "storage"],
            examples=["Read the configuration file", "Create a new directory"]
        ),
        AgentSkill(
            id="command_execution",
            name="Command Execution",
            description="Execute shell commands and scripts",
            tags=["shell", "commands", "execution"],
            examples=["Run the test suite", "Install dependencies"]
        ),
        AgentSkill(
            id="web_search",
            name="Web Search",
            description="Search the web for information",
            tags=["search", "web", "research"],
            examples=["Find documentation for this library", "Search for recent articles"]
        ),
        AgentSkill(
            id="mcp_tool_use",
            name="MCP Tool Use",
            description="Use Model Context Protocol tools",
            tags=["mcp", "tools", "integration"],
            examples=["Query the database", "Call an external API"]
        ),
        AgentSkill(
            id="task_delegation",
            name="Task Delegation",
            description="Delegate tasks to other agents",
            tags=["delegation", "coordination", "multi-agent"],
            examples=["Delegate this task to the research agent", "Coordinate with Archon"]
        )
    ],
    supports_extended_agent_card=False,
    icon_url="https://pmoves.ai/icon.png"
)
